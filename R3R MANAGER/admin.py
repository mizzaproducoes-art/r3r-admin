import streamlit as st
import pandas as pd
import re
import pdfplumber
from io import BytesIO

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM (CSS INJECTION) ---
st.set_page_config(page_title="R3R Enterprise", layout="wide", page_icon="🏢")

# Custom CSS para dar cara de SaaS e esconder marcas do Streamlit
st.markdown(
    """
    <style>
        /* Esconde Menu Burger e Rodapé */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Estilo dos Cards */
        div[data-testid="stMetric"] {
            background-color: #1E1E1E;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 10px;
            color: white;
        }
        
        /* Botão Principal (Download) */
        div.stDownloadButton > button {
            width: 100%;
            background-color: #00C853;
            color: white;
            font-weight: bold;
            border: none;
            padding: 15px;
            border-radius: 8px;
        }
        div.stDownloadButton > button:hover {
            background-color: #00E676;
            color: black;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# --- 2. MOTORES DE INTELIGÊNCIA (PARSERS BLINDADOS) ---


def parse_money(value_str):
    """Extrai dinheiro ignorando lixo, mas exigindo formato financeiro."""
    if not value_str:
        return None
    s = str(value_str).strip()
    if "R$" not in s and "," not in s:
        return None  # Proteção contra KM
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
    except:
        return None


def parse_km(value_str):
    """Extrai KM ignorando R$."""
    if not value_str:
        return 0
    s = str(value_str).strip()
    if "R$" in s or "," in s:
        return 0
    clean = re.sub(r"[^\d]", "", s)
    try:
        val = int(clean)
        return val if 0 <= val < 400000 else 0
    except:
        return 0


def clean_model_name(text):
    text = str(text).replace("\n", " ").replace('"', "").replace("'", "")
    text = re.sub(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", "", text)  # Remove Placa
    text = re.sub(r"R\$\s?[\d\.,]+", "", text)  # Remove Preços
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


# --- 3. DRIVERS DE LEITURA (ESTRATÉGIA UNIVERSAL) ---


def process_pdf_universal(file):
    """
    Tenta todas as estratégias possíveis.
    Retorna uma lista de carros ou lista vazia.
    """
    data_found = []

    with pdfplumber.open(file) as pdf:
        full_text = ""
        # 1. Tenta extrair texto bruto (para Regex)
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

        # ESTRATÉGIA A: Tabela Estruturada (Melhor para R3R/Alphaville)
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
                                        "Custo_Original": prices[1],
                                        "Origem": "Tabela",
                                    }
                                )
        except:
            pass

        # Se a estratégia A achou poucos carros (< 3) ou nenhum, tenta ESTRATÉGIA B
        if len(data_found) < 3:
            # ESTRATÉGIA B: Regex no Texto (Melhor para Mauá/Barueri/Genéricos)
            # Divide o texto por Placas
            parts = re.split(r"(\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b)", full_text)

            # Resetamos a lista para evitar duplicatas se a A achou algo parcial
            temp_data = []

            for i in range(1, len(parts) - 1, 2):
                placa = parts[i]
                content = parts[i + 1]  # Texto logo após a placa

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
                    # Tenta achar numero solto grande (Fallback KM)
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
                            "Custo_Original": prices[1],
                            "Origem": "Texto",
                        }
                    )

            # Se a estratégia B achou mais carros que a A, usamos a B
            if len(temp_data) > len(data_found):
                data_found = temp_data

    return data_found


# --- 4. INTERFACE DO DASHBOARD (SIDEBAR) ---
with st.sidebar:
    st.markdown("## 🏢 R3R Admin")
    st.markdown("---")

    st.markdown("### ⚙️ Configuração de Margem")
    margem_tipo = st.radio("Adicionar:", ["Valor Fixo (R$)", "Porcentagem (%)"])

    if margem_tipo == "Valor Fixo (R$)":
        margem_valor = st.number_input("Valor Extra (R$)", value=2000.0, step=100.0)
    else:
        margem_pct = st.number_input("Porcentagem Extra (%)", value=5.0, step=0.5)

    st.markdown("---")
    st.caption("Sistema v2.0 Enterprise")
    st.caption("Licenciado para: **R3R Repasses**")

# --- 5. ÁREA PRINCIPAL (DASHBOARD) ---
st.title("Gerenciador de Estoque & Precificação")
st.markdown("Importe as listas brutas e gere tabelas padronizadas para o grupo.")

# Área de Upload Estilizada
uploaded_file = st.file_uploader(
    "📂 Arraste o PDF da Fonte (Alphaville, Localiza, etc)", type="pdf"
)

if uploaded_file:
    with st.spinner("🔄 Processando Inteligência Artificial..."):
        try:
            data = process_pdf_universal(uploaded_file)

            if data:
                df = pd.DataFrame(data)

                # --- APLICAR REGRAS DE NEGÓCIO ---
                if margem_tipo == "Valor Fixo (R$)":
                    df["Preco_Venda"] = df["Custo_Original"] + margem_valor
                else:
                    df["Preco_Venda"] = df["Custo_Original"] * (1 + margem_pct / 100)

                # Cálculo de KPIs
                df["Lucro_Bruto_Previsto"] = df["Preco_Venda"] - df["Custo_Original"]

                # Ordenação Inteligente (Os mais baratos primeiro para vender rápido)
                df = df.sort_values(by="Preco_Venda", ascending=True)

                # --- DASHBOARD DE RESUMO ---
                st.markdown("### 📊 Resumo do Lote")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Veículos Detectados", len(df))
                col2.metric(
                    "Valor Total (Custo)", f"R$ {df['Custo_Original'].sum():,.0f}"
                )
                col3.metric("Valor Total (Venda)", f"R$ {df['Preco_Venda'].sum():,.0f}")
                col4.metric(
                    "Lucro Potencial",
                    f"R$ {df['Lucro_Bruto_Previsto'].sum():,.0f}",
                    delta="Estimado",
                )

                st.divider()

                # --- TABELA INTERATIVA ---
                st.subheader("📋 Prévia da Lista Formatada")
                # Fallback para coluna 'Ano' se não existir no df original
                if "Ano" not in df.columns:
                    df["Ano"] = "-"

                st.dataframe(
                    df[["Placa", "Modelo", "Ano", "KM", "Fipe", "Preco_Venda"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Preco_Venda": st.column_config.NumberColumn(
                            "💰 PREÇO R3R", format="R$ %.2f"
                        ),
                        "Fipe": st.column_config.NumberColumn(
                            "Tabela Fipe", format="R$ %.2f"
                        ),
                        "KM": st.column_config.NumberColumn("KM", format="%d km"),
                    },
                )

                # --- EXPORTAÇÃO (O PRODUTO FINAL) ---
                st.divider()

                # Gera Excel em memória
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    # Formatação Bonita no Excel
                    df_export = df[
                        ["Modelo", "Placa", "KM", "Ano", "Fipe", "Preco_Venda"]
                    ]
                    df_export.columns = [
                        "MODELO",
                        "PLACA",
                        "KM",
                        "ANO",
                        "TABELA FIPE",
                        "PREÇO R3R",
                    ]
                    df_export.to_excel(
                        writer, index=False, sheet_name="Oportunidades R3R"
                    )

                    # Ajuste de Colunas (Auto-width)
                    worksheet = writer.sheets["Oportunidades R3R"]
                    for i, col in enumerate(df_export.columns):
                        worksheet.set_column(i, i, 20)

                processed_data = output.getvalue()

                st.download_button(
                    label="📥 BAIXAR LISTA PRONTA PARA GRUPO (EXCEL)",
                    data=processed_data,
                    file_name="Lista_R3R_Oficial.xlsx",
                    mime="application/vnd.ms-excel",
                )

            else:
                st.warning(
                    "⚠️ O sistema leu o arquivo, mas não encontrou carros com preços claros."
                )
                st.info(
                    "Tente abrir o PDF e verificar se é uma imagem escaneada. O sistema precisa de texto."
                )

        except Exception as e:
            st.error("Erro inesperado no processamento.")
            st.code(e)
