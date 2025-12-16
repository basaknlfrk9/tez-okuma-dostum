import streamlit as st
from openai import OpenAI
import os

st.set_page_config(page_title="Dedektif Modu")
st.title("Dedektif Modu Açık")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Sifre Yok!")
    st.stop()
else:
    st.success("Sifre bulundu, sisteme girildi.")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

prompt = st.chat_input("Bir şey yaz (Örn: Selam)")

if prompt:
    st.write(f"Sen: {prompt}")
    st.info("1. Adım: OpenAI baglanmaya calisiyorum...")
