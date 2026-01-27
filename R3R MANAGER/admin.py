import streamlit as st
import pandas as pd
import re
import pdfplumber
from io import BytesIO

# --- CONFIGURAÇÃO VISUAL B2B ---
st.set_page_config(page_title="R3R Enterprise", layout="wide", page_icon="🏢")

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        div[data-testid="stMetric"] {
            background-color: #1E1E1E; border: 1px solid #333;
            padding: 15px; border-radius: 10px; color: white;
        }
        div.stDownloadButton > button {
            width: 100%; background-color: #00C853; color: white;
            font-weight: bold; padding: 15px; border-radius: 8px;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# --- MOTORES DE LEITURA (ATUALIZADO PARA ALPHAVILLE 27.01) ---


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
        return val if val > 2000 else None  # Filtra valores muito baixos
    except:
        return None


def clean_model_name(text):
    text = str(text).replace("\n", " ").replace('"', "").replace("'", "")
    # Remove padrões de placa e dinheiro para limpar o nome
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)
    text = re.sub(r"R\$\s?[\d\.,]+", "", text)
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
        "vcpbr",
        "vcper",
        "aprovado",
    ]
    words = text.split()
    clean = [
        w
        for w in words
        if w.lower() not in stopwords and len(w) > 2 and not w.isdigit()
    ]
    return " ".join(clean[:7])


def process_pdf_universal(file):
    data_found = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

            # Estratégia Híbrida (Linha a Linha para Alphaville Novo)
            lines = t.split("\n")
            for line in lines:
                # Busca Placa
                plate_match = re.search(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", line)
                if plate_match:
                    # Busca Dinheiro na mesma linha ou bloco
                    prices_raw = re.findall(r"R\$\s?[\d\.,]+", line)
                    prices = sorted(
                        [p for p in [parse_money(pr) for pr in prices_raw] if p],
                        reverse=True,
                    )

                    # Se achou poucos preços na linha, tenta olhar o contexto (linhas próximas)
                    if len(prices) < 2:
                        # Lógica de "Block Context" não implementada aqui por simplicidade,
                        # focando na linha que geralmente tem tudo no novo layout
                        pass

                    if len(prices) >= 2:
                        # Lógica Alphaville 27.01:
                        # Maior = Fipe
                        # Segundo Maior = Custo (Orçamento)
                        fipe = prices[0]
                        custo = prices[1]

                        # Proteção: Se o custo for muito baixo (ex: margem), ignora
                        if custo < 10000:
                            continue

                        # KM
                        km = 0
                        km_match = re.search(
                            r"(?:KM|Km)\s?(\d+)", line.replace(".", "")
                        )
                        if km_match:
                            km = int(km_match.group(1))

                        # Modelo
                        modelo = clean_model_name(line)

                        data_found.append(
                            {
                                "Placa": plate_match.group(),
                                "Modelo": modelo,
                                "KM": km,
                                "Fipe": fipe,
                                "Custo_Original": custo,
                            }
                        )

    # Se a estratégia linha a linha falhar, usa o "textão" bruto (Fallback)
    if len(data_found) < 2:
        parts = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)
        for i in range(1, len(parts) - 1, 2):
            placa = parts[i]
            content = parts[i + 1]
            prices_raw = re.findall(r"R\$\s?[\d\.,]+", content)
            prices = sorted(
                [p for p in [parse_money(pr) for pr in prices_raw] if p], reverse=True
            )

            if len(prices) >= 2:
                data_found.append(
                    {
                        "Placa": placa,
                        "Modelo": clean_model_name(content),
                        "KM": 0,
                        "Fipe": prices[0],
                        "Custo_Original": prices[1],
                    }
                )

    return data_found


# --- FRONTEND B2B ---
with st.sidebar:
    st.title("🏢 R3R Admin")
    st.divider()
    margem_tipo = st.radio("Adicionar:", ["Valor Fixo (R$)", "Porcentagem (%)"])
    if margem_tipo == "Valor Fixo (R$)":
        margem_valor = st.number_input("R$ Extra:", value=2000.0, step=100.0)
    else:
        margem_pct = st.number_input("% Extra:", value=5.0, step=0.5)

st.title("Gerador de Listas R3R 🚀")
st.caption("Compatível com novo layout Alphaville 2026")

uploaded_file = st.file_uploader("📂 PDF da Fonte", type="pdf")

if uploaded_file:
    with st.spinner("Processando novo layout..."):
        data = process_pdf_universal(uploaded_file)
        if data:
            df = pd.DataFrame(data)

            # Cálculos
            if margem_tipo == "Valor Fixo (R$)":
                df["Preco_Venda"] = df["Custo_Original"] + margem_valor
            else:
                df["Preco_Venda"] = df["Custo_Original"] * (1 + margem_pct / 100)

            df["Lucro_R3R"] = df["Preco_Venda"] - df["Custo_Original"]
            df = df.sort_values(by="Preco_Venda")

            # Dashboard
            c1, c2, c3 = st.columns(3)
            c1.metric("Veículos", len(df))
            c2.metric("Custo Total", f"R$ {df['Custo_Original'].sum():,.0f}")
            c3.metric("Lucro Previsto", f"R$ {df['Lucro_R3R'].sum():,.0f}")

            # Tabela
            st.dataframe(
                df[
                    [
                        "Placa",
                        "Modelo",
                        "Fipe",
                        "Custo_Original",
                        "Preco_Venda",
                        "Lucro_R3R",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Custo_Original": st.column_config.NumberColumn(
                        "🔴 Custo", format="R$ %.2f"
                    ),
                    "Preco_Venda": st.column_config.NumberColumn(
                        "🟢 Venda", format="R$ %.2f"
                    ),
                    "Lucro_R3R": st.column_config.NumberColumn(
                        "💰 Margem", format="R$ %.2f"
                    ),
                    "Fipe": st.column_config.NumberColumn("Fipe", format="R$ %.2f"),
                },
            )

            # Exportar
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_exp = df[
                    ["Modelo", "Placa", "KM", "Fipe", "Custo_Original", "Preco_Venda"]
                ]
                df_exp.columns = [
                    "MODELO",
                    "PLACA",
                    "KM",
                    "FIPE",
                    "CUSTO COMPRA",
                    "PREÇO VENDA",
                ]
                df_exp.to_excel(writer, index=False)

            st.download_button(
                "📥 BAIXAR EXCEL",
                output.getvalue(),
                "Lista_R3R.xlsx",
                "application/vnd.ms-excel",
            )
        else:
            st.error(
                "Não foi possível ler os dados. Verifique se o PDF contém texto selecionável."
            )
