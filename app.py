import streamlit as st from openai import OpenAI import os

st.set_page_config(page_title="Hata Testi")

st.title("⚠️ Hata Yakalama Modu")

if "OPENAI_API_KEY" not in st.secrets: st.error("API Anahtarı bulunamadı! Secrets ayarlarını kontrol et.") st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages: with st.chat_message(msg["role"]): st.write(msg["content"])

if prompt := st.chat_input("Bir şey yazın (Örn: Merhaba)"): st.session_state.messages.append({"role": "user", "content": prompt}) with st.chat_message("user"): st.write(prompt)

