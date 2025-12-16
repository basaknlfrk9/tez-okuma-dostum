import streamlit as st
from openai import OpenAI
import os
st.set_page_config(page_title="Hata Testi")
st.title("Test Modu")
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Sifre Yok!")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
prompt = st.chat_input("Mesaj yaz...")
if prompt:
    st.write(f"Sen: {prompt}")
    try:
        response = client.chat.completions.create(
model="gpt-3.5-turbo",
messages=[{"role": "user", "content": prompt}]
)
st.write(response.choices[0].message.content)
    except Exception as e:
    st.error(f"HATA: {e}")


