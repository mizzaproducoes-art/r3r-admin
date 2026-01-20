import streamlit as st

st.set_page_config(page_title="FipeHunter Test", layout="wide")

st.title("FipeHunter System Test")
st.write("Se você está vendo esta mensagem, o Streamlit está funcionando corretamente.")

password = st.text_input("Senha de Teste", type="password")
if st.button("Verificar"):
    if password == "FIPE2026":
        st.success("Acesso Permitido! O problema está no código principal.")
    else:
        st.error("Senha incorreta.")
