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

# --- DADOS ESTÁTICOS ---
LISTA_MARCAS = [
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
    "MERCEDES",
    "AUDI",
    "KIA",
    "CAOA CHERY",
    "RAM",
    "BYD",
    "GWM",
]
LISTA_CORES = [
    "BRANCO",
    "PRETO",
    "PRATA",
    "CINZA",
    "VERMELHO",
    "AZUL",
    "BEGE",
    "AMARELO",
    "VERDE",
    "MARROM",
    "DOURADO",
    "VINHO",
]
LISTA_ANOS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]


# --- LOGIN ---
def check_password():
    if st.session_state.get("authenticated", False):
        return True
    st.markdown("### 🔒 Acesso Restrito")
    pwd = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if pwd == "FIPE2026":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


if not check_password():
    st.stop()


# --- MOTOR DE LEITURA INTELIGENTE ---
def parse_money(value_str):
    if not value_str:
        return None
    clean = re.sub(r"[^\d,]", "", str(value_str))
    if not clean:
        return None
    try:
        val = (
            float(clean.replace(".", "").replace(",", "."))
            if "," in clean
            else float(clean.replace(".", ""))
        )
        return val if val > 2000 else None
    except:
        return None


def clean_info(text):
    text = str(text).upper()
    # Extrai Marca
    marca = "OUTROS"
    for m in LISTA_MARCAS:
        if m in text:
            marca = m
            break
    # Extrai Cor
    cor = "OUTROS"
    for c in LISTA_CORES:
        if c in text:
            cor = "BRANCO" if c == "BRANCA" else c
            break
    # Extrai Ano
    anos = re.findall(r"\b(20[1-2][0-9])\b", text)
    ano_mod = int(anos[1]) if len(anos) >= 2 else (int(anos[0]) if anos else 0)

    # Limpa Modelo
    clean = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)  # Placa
    clean = re.sub(r"R\$\s?[\d\.,]+", "", clean)  # Preço
    clean = re.sub(r"\b20[1-2][0-9]\b", "", clean)  # Ano
    words = clean.split()
    ignore = (
        [
            "OFERTA",
            "DISPONIVEL",
            "VCPBR",
            "VCPER",
            "APROVADO",
            "BARUERI",
            "ALPHAVILLE",
            "SP",
            "MARGIN",
            "FIPE",
            "ORCAMENTO",
        ]
        + LISTA_MARCAS
        + LISTA_CORES
    )
    modelo = " ".join(
        [w for w in words if w not in ignore and len(w) > 2 and not w.isdigit()][:6]
    )

    return marca, modelo, cor, ano_mod


def process_pdf(file):
    data = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        # Estratégia Texto (Melhor para layouts mistos)
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

        # Quebra por Placas
        parts = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)
        for i in range(1, len(parts) - 1, 2):
            placa = parts[i]
            ctx = parts[i + 1]  # Contexto após a placa

            # Extrai Dinheiro
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
                # Fipe é o maior, Repasse é o segundo maior (ignorando margens pequenas)
                fipe = prices[0]
                repasse = prices[1]
                if repasse < 10000:
                    continue  # Erro de leitura (pegou margem como preço)

                marca, modelo, cor, ano = clean_info(ctx)

                # KM (Tenta achar perto)
                km = 0
                km_match = re.search(
                    r"(\d{4,6})", ctx[:50]
                )  # Procura números grandes logo após a placa
                if km_match:
                    k_val = int(km_match.group(1))
                    if k_val < 300000:
                        km = k_val

                data.append(
                    {
                        "Marca": marca,
                        "Modelo": modelo,
                        "Cor": cor,
                        "Ano": ano,
                        "Placa": placa,
                        "KM": km,
                        "Fipe": fipe,
                        "Repasse": repasse,
                    }
                )
    return data


# --- SIDEBAR (FILTROS) ---
st.sidebar.header("🔍 Filtros Pré-Upload")
max_inv = st.sidebar.number_input("💰 Máx. Investimento:", step=5000.0)
sel_marcas = st.sidebar.multiselect("Montadora:", LISTA_MARCAS)
sel_anos = st.sidebar.multiselect("Ano:", LISTA_ANOS)
sel_cores = st.sidebar.multiselect("Cor:", LISTA_CORES)
txt_busca = st.sidebar.text_input("Buscar Modelo (ex: Corolla):")

# --- APP ---
st.title("🎯 FipeHunter Pro")

if uploaded_file := st.file_uploader("Arraste o PDF", type="pdf"):
    with st.spinner("Lendo direto da fonte..."):
        raw = process_pdf(uploaded_file)
        df = pd.DataFrame(raw)

        if not df.empty:
            final = []
            for _, row in df.iterrows():
                lucro = row["Fipe"] - row["Repasse"]
                margem = (lucro / row["Fipe"] * 100) if row["Fipe"] > 0 else 0

                # Filtros
                ok = True
                if max_inv > 0 and row["Repasse"] > max_inv:
                    ok = False
                if sel_marcas and row["Marca"] not in sel_marcas:
                    ok = False
                if sel_anos and row["Ano"] not in sel_anos:
                    ok = False
                if sel_cores and row["Cor"] not in sel_cores:
                    ok = False
                if txt_busca and txt_busca.upper() not in row["Modelo"]:
                    ok = False

                if ok and lucro > 0:
                    row["Lucro"] = lucro
                    row["Margem"] = margem
                    final.append(row)

            df_final = pd.DataFrame(final).sort_values(by="Lucro", ascending=False)

            if not df_final.empty:
                st.success(f"{len(df_final)} oportunidades encontradas!")

                # Top 3
                st.subheader("🔥 Melhores Ofertas")
                cols = st.columns(3)
                for i in range(min(3, len(df_final))):
                    r = df_final.iloc[i]
                    cols[i].metric(
                        f"{r['Marca']} {r['Modelo']}",
                        f"Lucro: R$ {r['Lucro']:,.0f}",
                        f"{r['Margem']:.1f}%",
                    )
                    cols[i].markdown(
                        f"**Paga:** R$ {r['Repasse']:,.0f} | **Fipe:** R$ {r['Fipe']:,.0f}"
                    )
                    cols[i].caption(f"{r['Cor']} | {r['Ano']} | {r['Placa']}")

                # Tabela
                st.divider()
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
                )

                # --- EXPORTAÇÃO (V1.6 RESTORED) ---
                st.divider()
                col_ex1, col_ex2 = st.columns(2)

                # 1. Excel Export (xlsxwriter)
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
                st.warning("Nenhum carro passou nos filtros.")
        else:
            st.error("Não consegui ler os carros. Verifique o PDF.")
