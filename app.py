import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Tez Asistanı", layout="wide")

st.title("Tez ve Makale Okuma Asistanı")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("API Anahtarı bulunamadı!")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "Merhaba! Bana bir PDF yükle, senin için okuyayım."
        }
    )

with st.sidebar:
    st.header("PDF Yükle")
    uploaded_file = st.file_uploader(
        "Dosyayı buraya bırak",
        type="pdf"
    )

for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

prompt = st.chat_input("Sorunuzu buraya yazın...")

if prompt:
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.write(prompt)
