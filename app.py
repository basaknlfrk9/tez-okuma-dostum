import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Okuma Dostum", page_icon="📚")

conn = st.connection("gsheets", type=GSheetsConnection)

def kullanici_kaydet(ad):
    try:
        df = conn.read()
    except:
        df = pd.DataFrame(columns=["Kullanici Adi", "Tarih"])

    yeni_satir = pd.DataFrame([{
        "Kullanici Adi": ad,
        "Tarih": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }])

    df = pd.concat([df, yeni_satir], ignore_index=True)
    conn.update(data=df)

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum'a Hoş Geldiniz")

    with st.form("giris"):
        isim = st.text_input("Lütfen adınızı yazın:")
        giris_btn = st.form_submit_button("Giriş Yap")

        if giris_btn and isim:
            st.session_state.user = isim
            kullanici_kaydet(isim)
            st.rerun()

else:
    st.title("📚 Okuma Dostum")
    st.sidebar.success(f"Kullanıcı: {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        del st.session_state.user
        st.rerun()

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Sorunuzu buraya yazın..."):
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=st.session_state.messages,
                stream=True,
            )
            response = st.write_stream(stream)

        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })

