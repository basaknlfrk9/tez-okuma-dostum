import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Okuma Dostum", layout="wide")

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")

    with st.form("giris"):
        isim = st.text_input("Adınızı yazın:")

        if st.form_submit_button("Giriş Yap") and isim:
            st.session_state.user = isim
            st.session_state.messages = []
            st.rerun()

else:
    st.sidebar.title(f"Merhaba {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap / Sıfırla"):
        st.session_state.clear()
        st.rerun()
