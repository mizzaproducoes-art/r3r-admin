import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="FipeHunter - v0.4", page_icon="🚜", layout="wide")


# --- FUNÇÕES ---
def clean_currency(value_str):
    if not value_str:
        return 0.0
    # Remove tudo que não é numérico, ponto ou vírgula
    clean_str = re.sub(r"[^\d,.]", "", str(value_str))

    # Lógica Brasil (vírgula decimal) vs Internacional
    if "," in clean_str:
        clean_str = clean_str.replace(".", "")  # Remove milhar
        clean_str = clean_str.replace(",", ".")  # Virgula vira ponto
    else:
        # Se só tem ponto, assume que é milhar (carro > 500 reais)
        clean_str = clean_str.replace(".", "")

    try:
        return float(clean_str)
    except:
        return 0.0


def extract_model_from_text(full_text):
    # Remove aspas de CSV e a placa
    text = full_text.replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)
    # Remove dinheiro
    text = re.sub(r"(?:R\$|RS|R|\$)\s?[\d\.\s,]+", "", text)

    words = text.split()
    stopwords = [
        "oferta",
        "disponivel",
        "sp",
        "barueri",
        "sorocaba",
        "campinas",
        "margem",
        "fipe",
        "preço",
    ]
    clean_words = [w for w in words if w.lower() not in stopwords and len(w) > 1]

    return " ".join(clean_words[:6])


def process_pdf_smart_mode(text):
    data = []
    # Regex Placa
    plate_pattern = r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b"
    # Regex Dinheiro (agora mais tolerante com espaços tipo "15 300")
    money_pattern = r"(?:R\$|RS|R|\$|MARGEM)\s?[\d\.\s,]+"

    lines = text.split("\n")
    current_car = None

    for line in lines:
        plate_match = re.search(plate_pattern, line)

        if plate_match:
            if current_car:
                finalize_car(current_car, data)
            current_car = {
                "placa": plate_match.group(),
                "full_text": line,
                "prices_raw": [],
                "year_model": "-",
            }

        if current_car:
            # Captura preços
            prices = re.findall(money_pattern, line, re.IGNORECASE)
            for p in prices:
                if len(re.sub(r"\D", "", p)) > 2:  # Ignora lixo curto
                    current_car["prices_raw"].append(p)

            # Captura Ano (2023, 2024/2025)
            if current_car["year_model"] == "-":
                year_match = re.search(r"\b(20[1-2][0-9])\b", line)
                if year_match:
                    current_car["year_model"] = year_match.group(0)

            current_car["full_text"] += " " + line

    if current_car:
        finalize_car(current_car, data)
    return pd.DataFrame(data)


def finalize_car(car, data_list):
    # Limpa valores
    clean_prices = []
    for p in car["prices_raw"]:
        val = clean_currency(p)
        if val > 3000:
            clean_prices.append(val)

    clean_prices = sorted(clean_prices, reverse=True)

    if len(clean_prices) >= 2:
        fipe = clean_prices[0]
        repasse = clean_prices[1]
        gross_margin = fipe - repasse

        ipva = 0.0

        # LÓGICA INTELIGENTE v0.4:
        # Verifica se o 3º valor é IPVA ou apenas a Margem repetida
        if len(clean_prices) > 2:
            third_val = clean_prices[2]

            # Se o 3º valor for muito parecido com a Margem Bruta, IGNORA (é redundância do PDF)
            difference = abs(gross_margin - third_val)
            if difference < 500:
                ipva = 0.0  # É lucro, não custo

            # Se for um valor menor (ex: 3k a 12k) e diferente do lucro, assume IPVA
            elif 2000 < third_val < 12000:
                ipva = third_val

        lucro_real = gross_margin - ipva

        if fipe > 0:
            margem_pct = (lucro_real / fipe) * 100

            # Filtros de sanidade
            if 3 < margem_pct < 70:
                data_list.append(
                    {
                        "Placa": car["placa"],
                        "Modelo": extract_model_from_text(car["full_text"]),
                        "Ano": car["year_model"],
                        "Fipe": fipe,
                        "Repasse": repasse,
                        "IPVA_Estimado": ipva,
                        "Lucro_Real": lucro_real,
                        "Margem_%": round(margem_pct, 1),
                        "Status": "Com IPVA" if ipva > 0 else "Sem taxas extras",
                    }
                )


# --- FRONTEND ---
st.title("🚜 FipeHunter v0.4")
st.caption("Multispectrum: Lê R3R, Barueri, Alphaville e Desmobja")

uploaded_file = st.file_uploader("Solte o PDF aqui", type="pdf")

if uploaded_file:
    with st.spinner("Processando inteligência de mercado..."):
        try:
            full_text = ""
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"

            df = process_pdf_smart_mode(full_text)

            if not df.empty:
                df = df.sort_values(by="Lucro_Real", ascending=False)

                # TOP 3
                st.divider()
                st.subheader("💎 Top 3 Oportunidades")
                cols = st.columns(3)
                for i in range(min(3, len(df))):
                    row = df.iloc[i]
                    cols[i].metric(
                        f"{row['Modelo'][:20]}..",
                        f"R$ {row['Lucro_Real']:,.0f}",
                        f"{row['Margem_%']}%",
                    )
                    cols[i].caption(f"{row['Placa']} | {row['Ano']}")

                # TABELA
                st.divider()
                st.dataframe(
                    df[
                        [
                            "Modelo",
                            "Ano",
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
                st.warning(
                    "Nenhum carro detectado. Verifique se o PDF é legível (texto)."
                )

        except Exception as e:
            st.error(f"Erro de leitura: {e}")
