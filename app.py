import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Tez Asistanı", layout="wide")

st.title("🎓 Tez Okuma & Sohbet Asistanı")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Lütfen API Anahtarınızı Secrets kısmına ekleyin.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Merhaba! Sol taraftan tezini (PDF) yükle, hemen inceleyelim."
        }
    ]

with st.sidebar:
    st.header("📂 PDF Yükleme Paneli")
    uploaded_file = st.file_uploader(
        "Dosyayı buraya bırak",
        type="pdf"
    )

for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if prompt := st.chat_input("Sorunuzu buraya yazın..."):
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.write(prompt)
