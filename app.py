import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Okuma Dostum", layout="wide")

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = []
        st.rerun()

else:
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

