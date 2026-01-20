import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM (Igual ao Admin) ---
st.set_page_config(page_title="FipeHunter Pro", layout="wide", page_icon="🎯")

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        div[data-testid="stMetric"] {
            background-color: #1E1E1E;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 10px;
            color: white;
        }
        div.stDownloadButton > button {
            width: 100%;
            background-color: #00C853;
            color: white;
            font-weight: bold;
            border: none;
            padding: 15px;
            border-radius: 8px;
        }
    </style>
""",
    unsafe_allow_html=True,
)


# --- 2. SISTEMA DE SEGURANÇA ---
def check_password():
    if st.session_state.get("authenticated", False):
        return True

    st.markdown("### 🔒 Acesso Restrito - FipeHunter")
    st.markdown("Digite a senha enviada no seu e-mail de compra.")
    password = st.text_input("Senha de Acesso", type="password")

    if st.button("Entrar"):
        if password == "FIPE2026":  # <--- SENHA
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
            return False
    return False


if not check_password():
    st.stop()

# --- 3. MOTORES DE INTELIGÊNCIA (Mesmo Core do Admin) ---


def parse_money(value_str):
    if not value_str:
        return None
    s = str(value_str).strip()
    if "R$" not in s and "," not in s:
        return None
    clean = re.sub(r"[^\d,]", "", s)
    if not clean:
        return None
    try:
        if "," in clean:
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(".", "")
        val = float(clean)
        return val if val > 2000 else None
    except Exception:
        return None


def parse_km(value_str):
    if not value_str:
        return 0
    s = str(value_str).strip()
    if "R$" in s or "," in s:
        return 0
    clean = re.sub(r"[^\d]", "", s)
    try:
        val = int(clean)
        return val if 0 <= val < 400000 else 0
    except Exception:
        return 0


def clean_model_name(text):
    text = str(text).replace("\n", " ").replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)
    text = re.sub(r"R\$\s?[\d\.,]+", "", text)
    stopwords = [
        "oferta",
        "disponivel",
        "sp",
        "barueri",
        "maua",
        "sorocaba",
        "campinas",
        "margem",
        "fipe",
        "preco",
        "ganho",
        "ipva",
        "km",
        "flex",
        "diesel",
        "manual",
        "automatico",
    ]
    words = text.split()
    clean = [
        w
        for w in words
        if w.lower() not in stopwords and len(w) > 2 and not w.isdigit()
    ]
    return " ".join(clean[:6])


# --- 4. DRIVERS DE LEITURA (UNIVERSAL) ---


def process_pdf_universal(file):
    data_found = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

        # ESTRATÉGIA A: Tabela
        try:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        row_str = " ".join([str(c) for c in row if c])
                        plate_match = re.search(
                            r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", row_str
                        )
                        if plate_match:
                            prices = []
                            km = 0
                            for cell in row:
                                c_str = str(cell).strip()
                                m = parse_money(c_str)
                                if m:
                                    prices.append(m)
                                else:
                                    k = parse_km(c_str)
                                    if k > km:
                                        km = k
                            prices = sorted(list(set(prices)), reverse=True)
                            if len(prices) >= 2:
                                data_found.append(
                                    {
                                        "Placa": plate_match.group(),
                                        "Modelo": clean_model_name(row_str),
                                        "KM": km,
                                        "Fipe": prices[0],
                                        "Repasse": prices[1],
                                    }
                                )
        except Exception:
            pass

        # ESTRATÉGIA B: Texto (Fallback)
        if len(data_found) < 3:
            parts = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)
            temp_data = []
            for i in range(1, len(parts) - 1, 2):
                placa = parts[i]
                content = parts[i + 1]
                prices_raw = re.findall(r"R\$\s?[\d\.,]+", content)
                prices = sorted(
                    [p for p in [parse_money(pr) for pr in prices_raw] if p],
                    reverse=True,
                )
                km = 0
                km_match = re.search(r"(?:KM|Km)\s?([\d\.]+)", content)
                if km_match:
                    km = parse_km(km_match.group(1))
                else:
                    loose = re.search(r"\b(\d{4,6})\b", content)
                    if loose and 0 < int(loose.group(1)) < 300000:
                        km = int(loose.group(1))

                if len(prices) >= 2:
                    temp_data.append(
                        {
                            "Placa": placa,
                            "Modelo": clean_model_name(content),
                            "KM": km,
                            "Fipe": prices[0],
                            "Repasse": prices[1],
                        }
                    )
            if len(temp_data) > len(data_found):
                data_found = temp_data
    return data_found


# --- 5. INTERFACE DO USUÁRIO (FILTROS + RESULTADOS) ---

# Sidebar Filtros
with st.sidebar:
    st.header("🔍 Filtros de Caça")
    max_invest = st.number_input(
        "💰 Tenho para investir até (R$):", min_value=0.0, value=0.0, step=5000.0
    )
    st.caption("Deixe 0,00 para ver tudo")
    target_km = st.slider("🚗 KM Máxima:", 0, 200000, 150000, step=5000)
    min_margin = st.slider("📈 Margem Mínima (%):", 0, 50, 10)
    st.markdown("---")
    st.caption("FipeHunter v1.2")

st.title("🎯 FipeHunter Pro")
st.markdown("### Inteligência Artificial para Repasses")

uploaded_file = st.file_uploader("Arraste seu PDF (Qualquer formato)", type="pdf")

if uploaded_file:
    with st.spinner("Caçando oportunidades..."):
        try:
            raw_data = process_pdf_universal(uploaded_file)

            # Filtros e Cálculos
            final_data = []
            for item in raw_data:
                lucro = item["Fipe"] - item["Repasse"]

                if item["Fipe"] > 0:
                    margem = (lucro / item["Fipe"]) * 100

                    pass_invest = (
                        True if max_invest == 0 else (item["Repasse"] <= max_invest)
                    )
                    pass_km = True if item["KM"] <= target_km else False
                    pass_margin = True if margem >= min_margin else False

                    if pass_invest and pass_km and pass_margin and (1 < margem < 70):
                        item["Lucro_Real"] = lucro
                        item["Margem_%"] = round(margem, 1)
                        final_data.append(item)

            df = pd.DataFrame(final_data)

            if not df.empty:
                df = df.sort_values(by="Lucro_Real", ascending=False)

                st.success(f"Encontramos {len(df)} oportunidades no seu perfil!")

                # --- TOP 3 CARDS (Agora com Preço de Compra) ---
                st.divider()
                st.subheader("🔥 Top 3 Oportunidades")
                cols = st.columns(3)
                for i in range(min(3, len(df))):
                    row = df.iloc[i]
                    val_km = f"{row['KM']:,.0f} km" if row["KM"] > 0 else "KM N/A"

                    # Formatação manual para Metrics (para garantir R$ certo)
                    lucro_fmt = (
                        f"R$ {row['Lucro_Real']:,.0f}".replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )
                    paga_fmt = (
                        f"R$ {row['Repasse']:,.0f}".replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )
                    fipe_fmt = (
                        f"R$ {row['Fipe']:,.0f}".replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )

                    cols[i].metric(
                        label=row["Modelo"],
                        value=f"Lucro: {lucro_fmt}",
                        delta=f"{row['Margem_%']}% Margem",
                    )
                    cols[i].markdown(f"💸 **Paga:** {paga_fmt}")
                    cols[i].caption(f"Fipe: {fipe_fmt} | {val_km}")
                    cols[i].markdown(f"`{row['Placa']}`")

                # --- TABELA DETALHADA ---
                st.divider()
                st.subheader("📋 Lista Completa")

                st.dataframe(
                    df[
                        [
                            "Modelo",
                            "Placa",
                            "Repasse",
                            "Fipe",
                            "KM",
                            "Lucro_Real",
                            "Margem_%",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Repasse": st.column_config.NumberColumn(
                            "🔴 Você Paga", format="R$ %.2f"
                        ),
                        "Fipe": st.column_config.NumberColumn("Fipe", format="R$ %.2f"),
                        "Lucro_Real": st.column_config.NumberColumn(
                            "🟢 Seu Lucro", format="R$ %.2f"
                        ),
                        "KM": st.column_config.NumberColumn("KM", format="%d km"),
                        "Margem_%": st.column_config.NumberColumn(
                            "Margem %", format="%.1f%%"
                        ),
                    },
                )
            else:
                st.warning(
                    "Nenhum carro passou nos seus filtros. Tente diminuir a margem ou aumentar o KM."
                )

        except Exception as e:
            st.error("Erro ao ler o arquivo. Verifique se é um PDF válido.")
