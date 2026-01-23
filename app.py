import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM ---
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
        if password == "FIPE2026":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
            return False
    return False


if not check_password():
    st.stop()

# --- 3. MOTORES DE EXTRAÇÃO (CÉREBRO) ---

CORES_VALIDAS = [
    "BRANCO",
    "BRANCA",
    "PRETO",
    "PRETA",
    "PRATA",
    "CINZA",
    "VERMELHO",
    "VERMELHA",
    "AZUL",
    "BEGE",
    "AMARELO",
    "AMARELA",
    "VERDE",
    "MARROM",
    "DOURADO",
    "LARANJA",
    "VINHO",
]


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


def extract_years(text):
    """Extrai anos nos formatos 2022, 2023 ou 22/23"""
    # Tenta formato curto 22/23
    short_years = re.search(r"\b(\d{2})/(\d{2})\b", text)
    if short_years:
        y1 = int(short_years.group(1)) + 2000
        y2 = int(short_years.group(2)) + 2000
        return y1, y2

    # Tenta formato longo 2022
    years = re.findall(r"\b(20[1-2][0-9])\b", text)
    unique_years = sorted(list(set([int(y) for y in years])))

    if len(unique_years) >= 2:
        return unique_years[0], unique_years[1]  # Fab, Mod
    elif len(unique_years) == 1:
        return unique_years[0], unique_years[0]

    return 0, 0  # Não encontrou


def extract_color(text):
    text_upper = text.upper()
    for cor in CORES_VALIDAS:
        if cor in text_upper:
            # Normaliza (BRANCA -> BRANCO)
            if cor == "BRANCA":
                return "BRANCO"
            if cor == "PRETA":
                return "PRETO"
            if cor == "VERMELHA":
                return "VERMELHO"
            if cor == "AMARELA":
                return "AMARELO"
            return cor
    return "OUTROS"


def clean_model_and_brand(text):
    text = str(text).replace("\n", " ").replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)
    text = re.sub(r"R\$\s?[\d\.,]+", "", text)
    text = re.sub(r"\b20[1-2][0-9]\b", "", text)  # Remove anos do nome

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
        "automático",
        "aut",
    ] + CORES_VALIDAS
    words = text.split()
    clean_words = [
        w
        for w in words
        if w.lower() not in [s.lower() for s in stopwords]
        and len(w) > 2
        and not w.isdigit()
    ]

    full_name = " ".join(clean_words[:6])

    # Extração de Marca
    marca = "OUTROS"
    if clean_words:
        first = clean_words[0].upper()
        if first in ["VW", "VOLKS", "VOLKSWAGEN"]:
            marca = "VOLKSWAGEN"
        elif first in ["GM", "CHEVROLET", "CHEV"]:
            marca = "CHEVROLET"
        elif first in ["FIAT"]:
            marca = "FIAT"
        elif first in ["TOYOTA"]:
            marca = "TOYOTA"
        elif first in ["HONDA"]:
            marca = "HONDA"
        elif first in ["HYUNDAI"]:
            marca = "HYUNDAI"
        elif first in ["JEEP"]:
            marca = "JEEP"
        elif first in ["RENAULT"]:
            marca = "RENAULT"
        elif first in ["NISSAN"]:
            marca = "NISSAN"
        elif first in ["PEUGEOT"]:
            marca = "PEUGEOT"
        elif first in ["CITROEN"]:
            marca = "CITROEN"
        elif first in ["FORD"]:
            marca = "FORD"
        elif first in ["BMW"]:
            marca = "BMW"
        elif first in ["MITSUBISHI"]:
            marca = "MITSUBISHI"
        else:
            marca = first

    return full_name, marca


# --- 4. DRIVERS DE LEITURA ---


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
                                modelo, marca = clean_model_and_brand(row_str)
                                ano_fab, ano_mod = extract_years(row_str)
                                cor = extract_color(row_str)

                                data_found.append(
                                    {
                                        "Marca": marca,
                                        "Modelo": modelo,
                                        "Placa": plate_match.group(),
                                        "Ano_Fab": ano_fab,
                                        "Ano_Mod": ano_mod,
                                        "Cor": cor,
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
                    modelo, marca = clean_model_and_brand(content)
                    ano_fab, ano_mod = extract_years(content)
                    cor = extract_color(content)

                    temp_data.append(
                        {
                            "Marca": marca,
                            "Modelo": modelo,
                            "Placa": placa,
                            "Ano_Fab": ano_fab,
                            "Ano_Mod": ano_mod,
                            "Cor": cor,
                            "KM": km,
                            "Fipe": prices[0],
                            "Repasse": prices[1],
                        }
                    )
            if len(temp_data) > len(data_found):
                data_found = temp_data
    return data_found


# --- 5. FRONTEND (BARRA LATERAL COM FILTROS) ---

st.sidebar.header("🔍 Filtros Gerais")
max_invest = st.sidebar.number_input(
    "💰 Investimento Máximo (R$):", min_value=0.0, value=0.0, step=5000.0
)
target_km = st.sidebar.slider("🚗 KM Máxima:", 0, 200000, 150000, step=5000)
min_margin = st.sidebar.slider("📈 Margem Mínima (%):", 0, 50, 10)

st.title("🎯 FipeHunter Pro")
st.markdown("### Inteligência Artificial para Repasses")

uploaded_file = st.file_uploader("Arraste seu PDF (Qualquer formato)", type="pdf")

if uploaded_file:
    with st.spinner("Lendo e classificando frota..."):
        try:
            raw_data = process_pdf_universal(uploaded_file)
            df = pd.DataFrame(raw_data)

            if not df.empty:
                # --- CRIAÇÃO DOS FILTROS ESPECÍFICOS (MARCA, ANO, COR) ---
                st.sidebar.divider()
                st.sidebar.header("🚙 Filtros de Veículo")

                # 1. Filtro de Marca
                todas_marcas = sorted(df["Marca"].unique())
                marcas_sel = st.sidebar.multiselect(
                    "Marca:", todas_marcas, default=todas_marcas
                )

                # 2. Filtro de Modelo (Dinâmico baseado na Marca)
                df_filtrado_marca = df[df["Marca"].isin(marcas_sel)]
                todos_modelos = sorted(df_filtrado_marca["Modelo"].unique())
                modelos_sel = st.sidebar.multiselect(
                    "Modelo:", todos_modelos, default=todos_modelos
                )

                # 3. Filtro de Ano Modelo
                todos_anos = sorted([x for x in df["Ano_Mod"].unique() if x > 0])
                if todos_anos:
                    anos_sel = st.sidebar.multiselect(
                        "Ano Modelo:", todos_anos, default=todos_anos
                    )
                else:
                    anos_sel = []

                # 4. Filtro de Cor
                todas_cores = sorted(df["Cor"].unique())
                cores_sel = st.sidebar.multiselect(
                    "Cor:", todas_cores, default=todas_cores
                )

                # --- APLICAÇÃO DOS FILTROS ---
                final_data = []

                # Filtrar o DataFrame principal com base nas seleções da Sidebar
                mask_marca = df["Marca"].isin(marcas_sel)
                mask_modelo = df["Modelo"].isin(modelos_sel)
                mask_ano = (
                    df["Ano_Mod"].isin(anos_sel)
                    if anos_sel
                    else pd.Series([True] * len(df), index=df.index)
                )
                mask_cor = df["Cor"].isin(cores_sel)

                df_filtered = df[mask_marca & mask_modelo & mask_ano & mask_cor]

                for index, item in df_filtered.iterrows():
                    lucro = item["Fipe"] - item["Repasse"]

                    if item["Fipe"] > 0:
                        margem = (lucro / item["Fipe"]) * 100

                        # Filtros Numéricos (Investimento, KM, Margem)
                        pass_invest = (
                            True if max_invest == 0 else (item["Repasse"] <= max_invest)
                        )
                        pass_km = True if item["KM"] <= target_km else False
                        pass_margin = True if margem >= min_margin else False

                        if (
                            pass_invest
                            and pass_km
                            and pass_margin
                            and (1 < margem < 70)
                        ):
                            row_dict = item.to_dict()
                            row_dict["Lucro_Real"] = lucro
                            row_dict["Margem_%"] = round(margem, 1)
                            final_data.append(row_dict)

                df_final = pd.DataFrame(final_data)

                if not df_final.empty:
                    df_final = df_final.sort_values(by="Lucro_Real", ascending=False)

                    st.success(f"Encontramos {len(df_final)} veículos no seu filtro!")

                    # --- TOP 3 CARDS ---
                    st.divider()
                    st.subheader("🔥 Top 3 Oportunidades")
                    cols = st.columns(3)
                    for i in range(min(3, len(df_final))):
                        row = df_final.iloc[i]

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
                        ano_str = (
                            f"{row['Ano_Fab']}/{row['Ano_Mod']}"
                            if row["Ano_Mod"] > 0
                            else "N/D"
                        )

                        cols[i].metric(
                            label=f"{row['Marca']} {row['Modelo']}",
                            value=f"Lucro: {lucro_fmt}",
                            delta=f"{row['Margem_%']}% Margem",
                        )
                        cols[i].markdown(f"**Cor:** {row['Cor']} | **Ano:** {ano_str}")
                        cols[i].markdown(f"💸 **Paga:** {paga_fmt}")
                        cols[i].caption(
                            f"Fipe: R$ {row['Fipe']:,.0f} | KM: {row['KM']}"
                        )
                        cols[i].markdown(f"`{row['Placa']}`")

                    # --- TABELA DETALHADA ---
                    st.divider()
                    st.subheader("📋 Lista Completa")

                    st.dataframe(
                        df_final[
                            [
                                "Marca",
                                "Modelo",
                                "Ano_Mod",
                                "Cor",
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
                            "Marca": "Montadora",
                            "Ano_Mod": st.column_config.NumberColumn(
                                "Ano", format="%d"
                            ),
                            "Repasse": st.column_config.NumberColumn(
                                "🔴 Você Paga", format="R$ %.2f"
                            ),
                            "Fipe": st.column_config.NumberColumn(
                                "Fipe", format="R$ %.2f"
                            ),
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
                        "Nenhum carro passou nos seus filtros. Tente liberar mais Marcas, Cores ou aumentar o limite de preço."
                    )
            else:
                st.warning(
                    "O arquivo foi lido, mas não encontramos carros válidos. Verifique se é um PDF de repasse."
                )

        except Exception as e:
            st.error("Erro ao processar arquivo.")
            st.code(e)
