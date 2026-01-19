import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="FipeHunter - MVP", page_icon="🚗", layout="wide")


# --- FUNÇÕES DE EXTRAÇÃO (CÉREBRO ATUALIZADO) ---
def clean_currency(value_str):
    """Limpa strings de moeda e converte para float."""
    if not value_str:
        return 0.0
    # Remove sujeira comum de OCR
    clean_str = re.sub(r"[^\d,]", "", str(value_str))
    clean_str = clean_str.replace(",", ".")
    try:
        return float(clean_str)
    except:
        return 0.0


def extract_car_data(line):
    """
    Tenta extrair Modelo, Ano, KM e Preços da linha.
    Suporta o formato com aspas do PDF Alphaville.
    """
    # Regex para capturar tudo que está entre aspas "..."
    columns = re.findall(r'"([^"]*)"', line)

    # Regex para capturar dinheiro solto na linha (fora ou dentro de aspas)
    money_pattern = r"(?:R\$|RS|R|\$)\s?[\d\.]+,[\d]{2}"
    prices_found = re.findall(money_pattern, line)
    prices = [clean_currency(p) for p in prices_found]
    # Filtra ruídos menores que R$ 500
    prices = [p for p in prices if p > 500]

    car_info = {
        "Placa": "Desconhecida",
        "Modelo": "Desconhecido",
        "Ano": "-",
        "KM": "-",
        "Prices": prices,
    }

    # Lógica para layout Alphaville (que usa "aspas")
    if len(columns) >= 4:
        # Geralmente: [0]Placa, [1]Modelo, [2]Ano Fab, [3]Ano Mod, [4]KM
        car_info["Placa"] = columns[0] if len(columns[0]) < 10 else "N/A"
        car_info["Modelo"] = columns[1]
        car_info["Ano"] = (
            f"{columns[2]}/{columns[3]}" if len(columns) > 3 else columns[2]
        )
        car_info["KM"] = columns[4] if len(columns) > 4 else "-"

    # Lógica Fallback (Layout Desmobja/Simples sem aspas claras)
    else:
        # Tenta achar placa via Regex
        plate_match = re.search(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", line)
        if plate_match:
            car_info["Placa"] = plate_match.group()
            # Tenta pegar o texto após a placa como modelo
            parts = line.split(car_info["Placa"])
            if len(parts) > 1:
                car_info["Modelo"] = (
                    parts[1][:20].strip() + "..."
                )  # Pega o começo do texto

    return car_info


def analyze_prices(car_info):
    """Define quem é Fipe, Repasse e IPVA baseado no tamanho do valor"""
    prices = sorted(car_info["Prices"], reverse=True)  # Maior para o menor

    item = {
        "Placa": car_info["Placa"],
        "Modelo": car_info["Modelo"],
        "Ano": car_info["Ano"],
        "KM": car_info["KM"],
        "Fipe": 0.0,
        "Repasse": 0.0,
        "Lucro_Real": 0.0,
        "Margem_%": 0.0,
        "Status": "Erro",
    }

    if len(prices) >= 2:
        # O MAIOR valor é sempre a FIPE (quase 100% dos casos)
        item["Fipe"] = prices[0]

        # O SEGUNDO maior é o Repasse (Preço que paga)
        item["Repasse"] = prices[1]

        # Se tiver um terceiro valor alto (mas menor que repasse), pode ser IPVA ou Margem bruta
        # Vamos calcular o lucro nós mesmos para garantir
        item["Lucro_Real"] = item["Fipe"] - item["Repasse"]

        # AJUSTE FINO: Se houver IPVA explícito (Alphaville costuma ter valores menores tipo 2k-5k)
        # Se sobrar um valor entre R$ 1.000 e R$ 15.000, abatemos do lucro
        potential_ipva = [p for p in prices[2:] if 1000 < p < 15000]
        if potential_ipva:
            ipva = potential_ipva[0]
            item["Lucro_Real"] -= ipva  # Abate IPVA
            item["Status"] = "Com IPVA desc."
        else:
            item["Status"] = "Sem IPVA ident."

        if item["Fipe"] > 0:
            item["Margem_%"] = round((item["Lucro_Real"] / item["Fipe"]) * 100, 1)

    return item


def process_pdf(raw_text):
    data = []
    lines = raw_text.split("\n")
    for line in lines:
        # Só processa linhas que parecem ter dados (tem placa e dinheiro)
        if re.search(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", line) and re.search(r"\$", line):
            car_raw = extract_car_data(line)
            car_final = analyze_prices(car_raw)
            if (
                car_final["Fipe"] > 0 and car_final["Margem_%"] < 50
            ):  # Filtra erros absurdos (>50% costuma ser erro)
                data.append(car_final)
    return pd.DataFrame(data)


# --- FRONTEND ---
st.title("🚜 FipeHunter v0.2")
st.caption("Versão corrigida: Modelo, Ano, KM e Lógica de Preço Inteligente")

uploaded_file = st.file_uploader("Arraste o PDF", type="pdf")

if uploaded_file:
    with st.spinner("Analisando..."):
        text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"

        df = process_pdf(text)

        if not df.empty:
            df = df.sort_values(by="Lucro_Real", ascending=False)

            # --- SNIPER MODE ---
            st.divider()
            st.subheader("🔥 Melhores Oportunidades")
            col1, col2, col3 = st.columns(3)

            top3 = df.head(3).to_dict("records")

            if len(top3) > 0:
                col1.metric(
                    f"🥇 {top3[0]['Modelo']}",
                    f"Lucro: R$ {top3[0]['Lucro_Real']:,.0f}",
                    f"Margem: {top3[0]['Margem_%']}%",
                )
                col1.caption(
                    f"{top3[0]['Ano']} | {top3[0]['KM']} km | Fipe: {top3[0]['Fipe']:,.0f}"
                )

            if len(top3) > 1:
                col2.metric(
                    f"🥈 {top3[1]['Modelo']}",
                    f"Lucro: R$ {top3[1]['Lucro_Real']:,.0f}",
                    f"Margem: {top3[1]['Margem_%']}%",
                )
                col2.caption(f"{top3[1]['Ano']} | {top3[1]['KM']} km")

            if len(top3) > 2:
                col3.metric(
                    f"🥉 {top3[2]['Modelo']}",
                    f"Lucro: R$ {top3[2]['Lucro_Real']:,.0f}",
                    f"Margem: {top3[2]['Margem_%']}%",
                )
                col3.caption(f"{top3[2]['Ano']} | {top3[2]['KM']} km")

            # --- TABELA ---
            st.divider()
            st.dataframe(
                df[
                    [
                        "Modelo",
                        "Ano",
                        "KM",
                        "Placa",
                        "Fipe",
                        "Repasse",
                        "Lucro_Real",
                        "Margem_%",
                        "Status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.error(
                "Nenhum carro encontrado. O PDF pode ser imagem (escaneado) ou formato desconhecido."
            )
