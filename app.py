import streamlit as st
from openai import OpenAI
import os

st.set_page_config(page_title="Hata Testi")

st.title("Test Ekranı")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Şifre Yok!")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

prompt = st.chat_input("Mesaj yaz...")

if prompt:
    st.write(f"Sen: {prompt}")
