import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="FipeHunter - MVP", page_icon="🚗", layout="wide")


# --- FUNÇÕES DE EXTRAÇÃO (BACKEND) ---
def clean_currency(value_str):
    """Limpa strings de moeda (R$ 1.000,00 -> 1000.0)"""
    if not value_str:
        return 0.0
    # Remove tudo que não é dígito ou vírgula
    clean_str = re.sub(r"[^\d,]", "", str(value_str))
    # Troca vírgula decimal por ponto
    clean_str = clean_str.replace(",", ".")
    try:
        return float(clean_str)
    except:
        return 0.0


def analyze_car_logic(car_dict, data_list):
    """
    Aplica a lógica de negócio:
    - Se encontrar 4 valores: Assume layout complexo (Margem, IPVA, Repasse, Fipe).
    - Se encontrar 3 valores: Assume layout simples (Fipe, Repasse, Margem).
    """
    # Limpa e filtra valores muito baixos (ruídos)
    prices = [clean_currency(p) for p in car_dict["prices"] if clean_currency(p) > 500]

    item = {
        "Placa": car_dict.get("placa", "N/A"),
        "Fipe": 0.0,
        "Repasse": 0.0,
        "IPVA": 0.0,
        "Lucro_Real": 0.0,
        "Margem_%": 0.0,
        "Status": "Erro",
        "Origem": "Desconhecida",
    }

    # Lógica Alphaville (IPVA Incluso no PDF mas deve ser descontado)
    if len(prices) >= 4:
        # Pega os últimos 4 valores confiáveis
        last_4 = prices[-4:]
        item["IPVA"] = last_4[1]  # 2º valor
        item["Repasse"] = last_4[2]  # 3º valor
        item["Fipe"] = last_4[3]  # 4º valor
        # Lucro Real = Fipe - Repasse - IPVA
        item["Lucro_Real"] = item["Fipe"] - item["Repasse"] - item["IPVA"]
        item["Status"] = "Alphaville (IPVA Incluso)"
        item["Origem"] = "PDF Complexo"

    # Lógica Desmobja (Layout Padrão)
    elif len(prices) >= 3:
        # Ordena: Maior (Fipe) -> Médio (Repasse) -> Menor (Margem PDF)
        sorted_prices = sorted(prices, reverse=True)
        item["Fipe"] = sorted_prices[0]
        item["Repasse"] = sorted_prices[1]
        # Lucro Real = Fipe - Repasse
        item["Lucro_Real"] = item["Fipe"] - item["Repasse"]
        item["Status"] = "Desmobja (Sem IPVA)"
        item["Origem"] = "PDF Padrão"

    # Adiciona se tiver dados válidos
    if item["Fipe"] > 0:
        item["Margem_%"] = round((item["Lucro_Real"] / item["Fipe"]) * 100, 1)
        data_list.append(item)


def process_fipehunter_text(raw_text):
    data = []
    # Regex ajustado para capturar Placas (Padrão novo e antigo)
    plate_pattern = r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"
    # Regex para capturar valores monetários (R$, RS, $, etc)
    money_pattern = r"(?:R\$|RS|R|\$)\s?[\d\.]+,[\d]{2}"

    lines = raw_text.split("\n")
    current_car = {}

    for line in lines:
        plate_match = re.search(plate_pattern, line)
        if plate_match:
            # Se já tinha um carro sendo processado, salva ele
            if current_car and "prices" in current_car:
                analyze_car_logic(current_car, data)
            # Começa novo carro
            current_car = {"placa": plate_match.group(), "prices": []}

        # Se tem um carro aberto, procura dinheiro na linha
        if current_car:
            prices_found = re.findall(money_pattern, line)
            if prices_found:
                current_car["prices"].extend(prices_found)

    # Processa o último da lista
    if current_car:
        analyze_car_logic(current_car, data)

    return pd.DataFrame(data)


# --- FRONTEND (STREAMLIT) ---
st.title("🚜 FipeHunter v0.1")
st.markdown("### O Detector de Oportunidades em Repasse")
st.markdown("Suba o PDF (Desmobja ou Alphaville) e veja o lucro real.")

uploaded_file = st.file_uploader("Arraste seu PDF aqui", type="pdf")

if uploaded_file:
    with st.spinner("Processando dados e calculando margens reais..."):
        try:
            # Extração de Texto
            all_text = ""
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"

            # Processamento
            df = process_fipehunter_text(all_text)

            if not df.empty:
                # Ordena por Lucro Real
                df = df.sort_values(by="Lucro_Real", ascending=False)

                # --- METRICAS DE SNIPER ---
                st.divider()
                st.subheader("🏆 Top Oportunidades (Lucro Líquido)")

                top3 = df.head(3).to_dict("records")
                col1, col2, col3 = st.columns(3)

                if len(top3) > 0:
                    col1.metric(
                        f"🥇 {top3[0]['Placa']}",
                        f"R$ {top3[0]['Lucro_Real']:,.0f}",
                        f"{top3[0]['Margem_%']}%",
                    )
                if len(top3) > 1:
                    col2.metric(
                        f"🥈 {top3[1]['Placa']}",
                        f"R$ {top3[1]['Lucro_Real']:,.0f}",
                        f"{top3[1]['Margem_%']}%",
                    )
                if len(top3) > 2:
                    col3.metric(
                        f"🥉 {top3[2]['Placa']}",
                        f"R$ {top3[2]['Lucro_Real']:,.0f}",
                        f"{top3[2]['Margem_%']}%",
                    )

                # --- TABELA DE DADOS ---
                st.divider()
                st.subheader("📋 Análise Detalhada")

                # Filtro interativo
                min_lucro = st.slider("Filtrar Lucro Mínimo (R$)", 0, 50000, 2000)
                df_show = df[df["Lucro_Real"] >= min_lucro]

                st.dataframe(
                    df_show[
                        [
                            "Placa",
                            "Fipe",
                            "Repasse",
                            "IPVA",
                            "Lucro_Real",
                            "Margem_%",
                            "Status",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning(
                    "Não encontrei carros no padrão esperado. Verifique se o PDF é de texto (não imagem escaneada)."
                )

        except Exception as e:
            st.error(f"Erro ao processar: {e}")
