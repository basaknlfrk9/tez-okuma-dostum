import streamlit as st from openai import OpenAI import os import json

st.set_page_config(page_title="Tez Okuma Dostum", layout="wide")

st.sidebar.title("Giriş") kullanici_adi = st.sidebar.text_input("Adınız:", value="Öğrenci")

if "OPENAI_API_KEY" not in st.secrets: st.error("API Anahtarı yok!") st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Merhaba!"}]

for msg in st.session_state.messages: with st.chat_message(msg["role"]): st.write(msg["content"])

prompt = st.chat_input("Buraya yazın...")

if prompt: st.session_state.messages.append({"role": "user", "content": prompt}) with st.chat_message("user"): st.write(prompt)
