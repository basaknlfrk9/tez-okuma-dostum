import streamlit as st
import requests

st.set_page_config(page_title="Kesin Tanı")
st.title("Kesin Tanı Testi")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Şifre Yok!")
    st.stop()

api_key = st.secrets["OPENAI_API_KEY"]

st.write(f"Anahtar Kontrol: {api_key[:7]}...")

if st.button("Bağlantıyı Test Et"):
    st.info("Sinyal gönderiliyor...")
