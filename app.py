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

# --- 3. MOTORES DE EXTRAÇÃO AVANÇADA (ETAPA NOVA) ---

# Lista de cores comuns para identificar no texto
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
    """Tenta extrair Ano Fab/Mod (ex: 2022/2023 ou 2022 2023)"""
    # Procura padrões de ano (2010 a 2030)
    years = re.findall(r"\b(20[1-2][0-9])\b", text)
    unique_years = sorted(list(set(years)))

    if len(unique_years) >= 2:
        return unique_years[0], unique_years[1]  # Fab, Mod
    elif len(unique_years) == 1:
        return unique_years[0], unique_years[0]
    return "N/D", "N/D"


def extract_color(text):
    """Busca a cor no texto baseado na lista de cores validas"""
    text_upper = text.upper()
    for cor in CORES_VALIDAS:
        if cor in text_upper:
            return cor
    return "N/D"


def clean_model_and_brand(text):
    """Limpa o nome e extrai a marca"""
    text = str(text).replace("\n", " ").replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)  # Remove Placa
    text = re.sub(r"R\$\s?[\d\.,]+", "", text)  # Remove Preços

    # Remove anos soltos no nome
    text = re.sub(r"\b20[1-2][0-9]\b", "", text)

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

    # Extração de Marca (Primeira palavra geralmente)
    marca = "OUTROS"
    if clean_words:
        first = clean_words[0].upper()
        # Ajustes comuns
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
        else:
            marca = first

    return full_name, marca


# --- 4. DRIVERS DE LEITURA (UNIVERSAL) ---


def process_pdf_universal(file):
    data_found = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

        # ESTRATÉGIA A: Tabela (R3R, Alphaville)
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

        # ESTRATÉGIA B: Texto (Fallback - Mauá, Barueri)
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


# --- 5. INTERFACE DO USUÁRIO (NOVOS FILTROS) ---

# Sidebar Filtros
with st.sidebar:
    st.header("🔍 Filtros de Caça")

    # Filtros Financeiros
    max_invest = st.number_input(
        "💰 Investimento Máximo (R$):", min_value=0.0, value=0.0, step=5000.0
    )
    target_km = st.slider("🚗 KM Máxima:", 0, 200000, 150000, step=5000)
    min_margin = st.slider("📈 Margem Mínima (%):", 0, 50, 10)

    st.divider()

    # Placeholder para filtros dinâmicos (Marca/Modelo)
    st.info("Carregue um PDF para habilitar filtros de Marca e Modelo.")

st.title("🎯 FipeHunter Pro")
st.markdown("### Inteligência Artificial para Repasses")

uploaded_file = st.file_uploader("Arraste seu PDF (Qualquer formato)", type="pdf")

if uploaded_file:
    with st.spinner("Analisando frota, cores e anos..."):
        try:
            raw_data = process_pdf_universal(uploaded_file)

            # --- PÓS-PROCESSAMENTO PARA DATAFRAME ---
            df = pd.DataFrame(raw_data)

            if not df.empty:
                # 1. Criação dos Filtros Dinâmicos na Sidebar (Agora que temos dados)
                with st.sidebar:
                    st.divider()
                    st.header("🚙 Filtros de Veículo")

                    # Filtro de Marca
                    todas_marcas = sorted(df["Marca"].unique())
                    marcas_sel = st.multiselect(
                        "Filtrar Marca:", todas_marcas, default=todas_marcas
                    )

                    # Filtro de Modelo (Baseado na Marca)
                    df_marcas = df[df["Marca"].isin(marcas_sel)]
                    todos_modelos = sorted(df_marcas["Modelo"].unique())
                    modelos_sel = st.multiselect(
                        "Filtrar Modelo:", todos_modelos, default=todos_modelos
                    )

                # 2. Aplicação dos Filtros
                final_data = []
                for index, item in df.iterrows():
                    lucro = item["Fipe"] - item["Repasse"]
                    if item["Fipe"] > 0:
                        margem = (lucro / item["Fipe"]) * 100

                        # Checagem de Filtros
                        pass_invest = (
                            True if max_invest == 0 else (item["Repasse"] <= max_invest)
                        )
                        pass_km = True if item["KM"] <= target_km else False
                        pass_margin = True if margem >= min_margin else False
                        pass_marca = item["Marca"] in marcas_sel
                        pass_modelo = item["Modelo"] in modelos_sel

                        if (
                            pass_invest
                            and pass_km
                            and pass_margin
                            and pass_marca
                            and pass_modelo
                            and (1 < margem < 70)
                        ):
                            item_dict = item.to_dict()
                            item_dict["Lucro_Real"] = lucro
                            item_dict["Margem_%"] = round(margem, 1)
                            final_data.append(item_dict)

                df_final = pd.DataFrame(final_data)

                if not df_final.empty:
                    df_final = df_final.sort_values(by="Lucro_Real", ascending=False)

                    st.success(f"Encontramos {len(df_final)} veículos no seu perfil!")

                    # --- TOP 3 CARDS ---
                    st.divider()
                    st.subheader("🔥 Top 3 Oportunidades")
                    cols = st.columns(3)
                    for i in range(min(3, len(df_final))):
                        row = df_final.iloc[i]

                        # Formatação
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

                        cols[i].metric(
                            label=f"{row['Marca']} {row['Modelo']}",
                            value=f"Lucro: {lucro_fmt}",
                            delta=f"{row['Margem_%']}% Margem",
                        )
                        cols[i].markdown(
                            f"**Cor:** {row['Cor']} | **Ano:** {row['Ano_Fab']}/{row['Ano_Mod']}"
                        )
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
                        "Nenhum carro passou nos seus filtros. Tente liberar mais Marcas ou aumentar o limite de preço."
                    )
            else:
                st.warning(
                    "O arquivo foi lido, mas não encontramos carros válidos. Verifique se é um PDF de repasse."
                )

        except Exception as e:
            st.error("Erro ao processar arquivo.")
            with st.expander("Erro Técnico"):
                st.code(e)
