import streamlit as st
import pandas as pd
import re
import pdfplumber
from io import BytesIO

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="R3R Enterprise", layout="wide", page_icon="🏢")
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


# --- MOTOR DE LEITURA (ALPHAVILLE 15 COLUNAS) ---
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
        return val
    except:
        return None


def extract_details(text):
    # Limpeza básica
    text = text.replace("\n", " ").upper()

    # Extração de Ano (ex: 2023 2024)
    anos = re.findall(r"\b(20[1-3][0-9])\b", text)
    ano_fab = anos[0] if len(anos) > 0 else "N/D"
    ano_mod = anos[1] if len(anos) > 1 else ano_fab

    # Extração de Cor (Lista expandida baseada no PDF)
    cores = [
        "BRANCO",
        "BRANCA",
        "PRETO",
        "PRETA",
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
        "LARANJA",
    ]
    cor_encontrada = "OUTROS"
    for c in cores:
        if c in text:
            cor_encontrada = c.replace("BRANCA", "BRANCO").replace("PRETA", "PRETO")
            break

    # Limpeza de Modelo
    ignore = [
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
        "LOJA",
        "ENDEREÇO",
    ] + cores
    clean_text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)  # Remove Placa
    clean_text = re.sub(r"R\$\s?[\d\.,]+", "", clean_text)  # Remove Preços
    clean_text = re.sub(r"\b20[1-3][0-9]\b", "", clean_text)  # Remove Anos

    words = clean_text.split()
    modelo = " ".join(
        [w for w in words if w not in ignore and len(w) > 2 and not w.isdigit()][:7]
    )

    return modelo, ano_fab, ano_mod, cor_encontrada


def process_pdf_alphaville(file):
    data = []
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

        # Quebra por Placa (Padrão Mercosul ou Antigo) - Referência da Tabela
        entries = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)

        for i in range(1, len(entries) - 1, 2):
            placa = entries[i]
            content = entries[i + 1]  # Todo o texto após a placa até a próxima

            # Extração de Valores Monetários
            prices_raw = re.findall(r"R\$\s?[\d\.,]+", content)
            prices = sorted(
                [p for p in [parse_money(m) for m in prices_raw] if p is not None],
                reverse=True,
            )

            # Lógica Alphaville: Maior=Fipe, Segundo=Custo, Menor=Margem
            if len(prices) >= 2:
                fipe = prices[0]
                custo = prices[1]  # O valor que o Renan paga

                # Proteção: Se o custo for muito baixo (ex: <10k), provavelmente pegou a margem como custo
                if custo < 10000 and len(prices) > 2:
                    custo = prices[0]  # Fallback

                if custo > 5000:  # Filtra lixo
                    # Extração de KM (Geralmente um número solto no texto antes dos preços)
                    km = 0
                    km_match = re.search(r"(?:KM)?\s?(\d{2,3}\.?\d{3})", content)
                    if km_match:
                        try:
                            km = int(km_match.group(1).replace(".", ""))
                        except:
                            pass

                    modelo, ano_fab, ano_mod, cor = extract_details(content)

                    data.append(
                        {
                            "Placa": placa,
                            "Modelo": modelo,
                            "Ano": f"{ano_fab}/{ano_mod}",
                            "Cor": cor,
                            "KM": km,
                            "Fipe": fipe,
                            "Custo_Original": custo,
                        }
                    )
    return data


# --- SIDEBAR B2B ---
st.sidebar.title("🏢 R3R Admin")
st.sidebar.divider()
st.sidebar.header("Margem R3R")
margem_valor = st.sidebar.number_input(
    "Adicionar Valor Fixo (R$):", value=2000.0, step=100.0
)

# --- APP PRINCIPAL ---
st.title("Importador Alphaville Oficial 🚀")
uploaded = st.file_uploader("Subir PDF (Layout 15 Colunas)", type="pdf")

if uploaded:
    with st.spinner("Processando Inteligência de Dados..."):
        raw_data = process_pdf_alphaville(uploaded)
        df = pd.DataFrame(raw_data)

        if not df.empty:
            # Cálculos
            df["Preco_Venda"] = df["Custo_Original"] + margem_valor
            df["Lucro_R3R"] = df["Preco_Venda"] - df["Custo_Original"]
            df = df.sort_values(by="Preco_Venda")

            # Dashboard
            c1, c2, c3 = st.columns(3)
            c1.metric("Veículos", len(df))
            c2.metric("Total Compra", f"R$ {df['Custo_Original'].sum():,.0f}")
            c3.metric("Lucro Estimado", f"R$ {df['Lucro_R3R'].sum():,.0f}")

            # Tabela
            st.dataframe(
                df[
                    [
                        "Placa",
                        "Modelo",
                        "Ano",
                        "Cor",
                        "Fipe",
                        "Custo_Original",
                        "Preco_Venda",
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
                    "Fipe": st.column_config.NumberColumn("Fipe", format="R$ %.2f"),
                },
            )

            # Exportar Excel Padronizado
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_exp = df[
                    [
                        "Modelo",
                        "Placa",
                        "Ano",
                        "Cor",
                        "KM",
                        "Fipe",
                        "Custo_Original",
                        "Preco_Venda",
                    ]
                ]
                df_exp.columns = [
                    "MODELO",
                    "PLACA",
                    "ANO",
                    "COR",
                    "KM",
                    "FIPE",
                    "CUSTO",
                    "VENDA",
                ]
                df_exp.to_excel(writer, index=False)

            st.download_button(
                "📥 BAIXAR EXCEL R3R",
                output.getvalue(),
                "Lista_R3R_Oficial.xlsx",
                "application/vnd.ms-excel",
            )
        else:
            st.error(
                "Erro de Leitura. Verifique se o PDF segue o padrão Alphaville/Localiza novo."
            )
