import streamlit as st
import pandas as pd
import re
import pdfplumber
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="FipeHunter Pro", layout="wide", page_icon="🎯")
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        div[data-testid="stMetric"] { background-color: #1E1E1E; border: 1px solid #333; padding: 15px; border-radius: 10px; color: white; }
        div.stDownloadButton > button { width: 100%; background-color: #00C853; color: white; font-weight: bold; padding: 15px; border-radius: 8px; }
    </style>
""",
    unsafe_allow_html=True,
)

# --- FILTROS PRÉ-CARREGADOS ---
MARCAS = [
    "CHEVROLET",
    "VOLKSWAGEN",
    "FIAT",
    "TOYOTA",
    "HONDA",
    "HYUNDAI",
    "JEEP",
    "RENAULT",
    "NISSAN",
    "PEUGEOT",
    "CITROEN",
    "FORD",
    "MITSUBISHI",
    "BMW",
]
CORES = ["BRANCO", "PRETO", "PRATA", "CINZA", "VERMELHO", "AZUL", "BEGE", "VERDE"]
ANOS = [2026, 2025, 2024, 2023, 2022, 2021, 2020]


# --- LOGIN ---
def check_password():
    if st.session_state.get("auth", False):
        return True
    st.markdown("### 🔒 Acesso Restrito - FipeHunter")
    pwd = st.text_input("Senha de Acesso", type="password")
    if st.button("Entrar"):
        if pwd == "FIPE2026":
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Senha Incorreta")
    return False


if not check_password():
    st.stop()


# --- MOTOR DE LEITURA (MESMO DO B2B) ---
def parse_money(v):
    try:
        return float(re.sub(r"[^\d,]", "", str(v)).replace(".", "").replace(",", "."))
    except:
        return None


def process_pdf(file):
    data = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

        parts = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)
        for i in range(1, len(parts) - 1, 2):
            placa = parts[i]
            ctx = parts[i + 1].replace("\n", " ").upper()

            prices = sorted(
                [
                    p
                    for p in [
                        parse_money(m) for m in re.findall(r"R\$\s?[\d\.,]+", ctx)
                    ]
                    if p
                ],
                reverse=True,
            )
            if len(prices) >= 2:
                fipe = prices[0]
                repasse = prices[1]
                if repasse < 10000:
                    continue

                # Dados Texto
                marca = "OUTROS"
                for m in MARCAS:
                    if m in ctx:
                        marca = m
                        break

                cor = "OUTROS"
                for c in CORES:
                    if c in ctx:
                        cor = c
                        break

                anos = re.findall(r"\b(20[1-3][0-9])\b", ctx)
                ano = int(anos[1]) if len(anos) > 1 else (int(anos[0]) if anos else 0)

                # Modelo Limpo
                ignore = (
                    ["OFERTA", "VCPBR", "SP", "BARUERI", "ALPHAVILLE"] + MARCAS + CORES
                )
                clean = re.sub(r"R\$\s?[\d\.,]+", "", ctx)
                clean = re.sub(r"\b20[1-3][0-9]\b", "", clean)
                modelo = " ".join(
                    [
                        w
                        for w in clean.split()
                        if w not in ignore and len(w) > 2 and not w.isdigit()
                    ][:6]
                )

                data.append(
                    {
                        "Marca": marca,
                        "Modelo": modelo,
                        "Ano": ano,
                        "Cor": cor,
                        "Placa": placa,
                        "Fipe": fipe,
                        "Repasse": repasse,
                    }
                )
    return data


# --- FRONTEND ---
st.sidebar.header("🔍 Filtros Pré-Upload")
sel_marcas = st.sidebar.multiselect("Montadora:", MARCAS)
sel_anos = st.sidebar.multiselect("Ano Modelo:", ANOS)
max_val = st.sidebar.number_input("💰 Máx. Investimento (R$):", step=5000)

st.title("🎯 FipeHunter Pro")
uploaded = st.file_uploader("Arraste o PDF Alphaville aqui", type="pdf")

if uploaded:
    with st.spinner("Analisando Oportunidades..."):
        raw = process_pdf(uploaded)
        df = pd.DataFrame(raw)

        if not df.empty:
            final = []
            for _, r in df.iterrows():
                lucro = r["Fipe"] - r["Repasse"]
                margem = (lucro / r["Fipe"]) * 100 if r["Fipe"] > 0 else 0

                # Filtros
                ok = True
                if sel_marcas and r["Marca"] not in sel_marcas:
                    ok = False
                if sel_anos and r["Ano"] not in sel_anos:
                    ok = False
                if max_val > 0 and r["Repasse"] > max_val:
                    ok = False

                if ok and lucro > 0:
                    r["Lucro"] = lucro
                    r["Margem"] = margem
                    final.append(r)

            df_final = pd.DataFrame(final).sort_values("Lucro", ascending=False)

            if not df_final.empty:
                st.success(f"{len(df_final)} veículos encontrados!")

                # Tabela Principal
                st.dataframe(
                    df_final[
                        [
                            "Marca",
                            "Modelo",
                            "Ano",
                            "Cor",
                            "Repasse",
                            "Fipe",
                            "Lucro",
                            "Margem",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                # --- EXPORTAÇÃO (RESTAURADA) ---
                st.divider()
                col_ex1, col_ex2 = st.columns(2)

                # 1. Excel Export
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_final.to_excel(writer, index=False, sheet_name="Oportunidades")
                excel_data = output.getvalue()

                col_ex1.download_button(
                    label="📥 Exportar Excel (.xlsx)",
                    data=excel_data,
                    file_name="fipehunter_oportunidades.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                # 2. CSV Export
                csv = df_final.to_csv(index=False).encode("utf-8")
                col_ex2.download_button(
                    label="📄 Exportar CSV",
                    data=csv,
                    file_name="fipehunter_oportunidades.csv",
                    mime="text/csv",
                )
            else:
                st.warning("Nenhum carro passou nos filtros configurados.")
        else:
            st.error("PDF não reconhecido ou sem dados extraíveis.")
else:
    st.info("👈 Configure os filtros na lateral e suba o PDF Alphaville mais recente.")
