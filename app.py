import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Tez Asistanı")

st.title("Tez Okuma Asistanı")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Sifre Yok!")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    uploaded_file = st.file_uploader("PDF Yukle", type="pdf")

    if uploaded_file and "okundu" not in st.session_state:
        reader = PyPDF2.PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            text += page.extract_text()

        st.session_state.messages.append(
            {"role": "system", "content": text}
        )
        st.session_state.okundu = True
        st.success("PDF Tamam!")

for msg in st.session_state.messages:
    if msg["role"] != "system":
        st.chat_message(msg["role"]).write(msg["content"])

prompt = st.chat_input("Sorunu yaz...")

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        msg = response.choices[0].message.content
        st.chat_message("assistant").write(msg)
        st.session_state.messages.append(
            {"role": "assistant", "content": msg}
        )
    except Exception as e:
        st.error(e)
