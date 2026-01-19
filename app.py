import streamlit as st
import pandas as pd
import re
import pdfplumber

st.set_page_config(page_title="FipeHunter v0.5", page_icon="🚜", layout="wide")


def clean_currency(value_str):
    if not value_str:
        return 0.0
    # Limpa sujeira e padroniza float
    clean = re.sub(r"[^\d,.]", "", str(value_str))
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    else:
        clean = clean.replace(".", "")
    try:
        return float(clean)
    except:
        return 0.0


def extract_model_generic(text):
    # Limpa aspas, placas e valores monetários para sobrar o nome
    text = text.replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)
    text = re.sub(r"(?:R\$|RS|R|\$)\s?[\d\.\s,]+", "", text)

    # Remove palavras proibidas (cidades, rótulos comuns)
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
        "cliente",
        "ganho",
        "ipva",
        "cidade",
        "atualizado",
        "patio",
        "localização",
        "veiculo",
        "modelo",
    ]

    words = text.split()
    clean_words = [
        w
        for w in words
        if w.lower() not in stopwords and len(w) > 2 and not w.isdigit()
    ]
    return " ".join(clean_words[:5])  # Pega as primeiras 5 palavras do modelo


def process_universal(text):
    data = []
    # Regex Genérico de Dinheiro (captura qualquer R$ ...)
    money_pattern = r"(?:R\$|RS|R|\$)\s?[\d\.\s,]+"
    # Regex de Placa
    plate_pattern = r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b"

    lines = text.split("\n")
    current_car = None

    for line in lines:
        plate_match = re.search(plate_pattern, line)

        if plate_match:
            if current_car:
                finalize_car_universal(current_car, data)
            current_car = {
                "placa": plate_match.group(),
                "full_text": line,
                "money_values": [],
                "year": "-",
            }

        if current_car:
            # Captura todos os valores monetários
            raw_prices = re.findall(money_pattern, line, re.IGNORECASE)
            for p in raw_prices:
                val = clean_currency(p)
                if val > 3000:  # Ignora valores baixos
                    current_car["money_values"].append(val)

            # Captura Ano
            if current_car["year"] == "-":
                ym = re.search(r"\b(20[1-2][0-9])\b", line)
                if ym:
                    current_car["year"] = ym.group(0)

            current_car["full_text"] += " " + line

    if current_car:
        finalize_car_universal(current_car, data)
    return pd.DataFrame(data)


def finalize_car_universal(car, data_list):
    # LÓGICA DO TRATOR:
    # 1. Ordena todos os valores encontrados do maior para o menor.
    # 2. Assume: Maior = Fipe, Segundo Maior = Repasse.
    # 3. Ignora o resto (lucro explícito, ipva, taxas). Recalcula tudo.

    prices = sorted(list(set(car["money_values"])), reverse=True)

    if len(prices) >= 2:
        fipe = prices[0]
        repasse = prices[1]

        # Trava de segurança: Se o repasse for muito baixo (<30% da Fipe), é erro de leitura.
        if repasse < (fipe * 0.3):
            if len(prices) > 2:
                repasse = prices[2]  # Tenta o próximo valor
            else:
                return  # Aborta carro com dados estranhos

        lucro_real = fipe - repasse
        margem_pct = (lucro_real / fipe) * 100

        # Filtro de Sanidade (Margem entre 5% e 60%)
        if 5 < margem_pct < 60:
            data_list.append(
                {
                    "Placa": car["placa"],
                    "Modelo": extract_model_generic(car["full_text"]),
                    "Ano": car["year"],
                    "Fipe": fipe,
                    "Repasse": repasse,
                    "Lucro_Estimado": lucro_real,
                    "Margem_%": round(margem_pct, 1),
                }
            )


# --- FRONTEND ---
st.title("🚜 FipeHunter v0.5 (Universal)")
st.caption("O Trator: Lê qualquer lista baseada na hierarquia de valores.")

uploaded_file = st.file_uploader("Solte seu PDF", type="pdf")

if uploaded_file:
    with st.spinner("O Trator está passando..."):
        try:
            full_text = ""
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"

            df = process_universal(full_text)

            if not df.empty:
                df = df.sort_values(by="Lucro_Estimado", ascending=False)

                # TOP CARDS
                st.divider()
                st.subheader("🔥 Melhores Oportunidades")
                cols = st.columns(3)
                for i in range(min(3, len(df))):
                    row = df.iloc[i]
                    cols[i].metric(
                        f"{row['Modelo']}",
                        f"R$ {row['Lucro_Estimado']:,.0f}",
                        f"{row['Margem_%']}%",
                    )
                    cols[i].caption(f"{row['Ano']} | Fipe: {row['Fipe']:,.0f}")

                # TABLE
                st.divider()
                st.dataframe(
                    df[
                        [
                            "Modelo",
                            "Ano",
                            "Placa",
                            "Fipe",
                            "Repasse",
                            "Lucro_Estimado",
                            "Margem_%",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.error(
                    "Não consegui extrair dados. O PDF pode ser imagem ou ter layout muito atípico."
                )

        except Exception as e:
            st.error(f"Erro: {e}")
