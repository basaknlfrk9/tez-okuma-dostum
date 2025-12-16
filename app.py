import streamlit as st
from openai import OpenAI
import PyPDF2
import pandas as pd
import os
import json
from datetime import datetime

st.set_page_config(page_title="Tez Asistanı", layout="wide")

excel_file = "kullanicilar.xlsx"


def kullanici_kaydet(kullanici_adi):
    try:
        if not os.path.exists(excel_file):
            df = pd.DataFrame(columns=["Ad", "Tarih"])
            df.to_excel(excel_file, index=False)
        else:
            df = pd.read_excel(excel_file)
        yeni = pd.DataFrame(
            [[kullanici_adi, datetime.now()]],
            columns=["Ad", "Tarih"]
        )
        df = pd.concat([df, yeni], ignore_index=True)
        df.to_excel(excel_file, index=False)
    except:
        pass


def gecmis_yukle(kullanici_adi):
    dosya = f"{kullanici_adi}.json"
    if os.path.exists(dosya):
        with open(dosya, "r") as f:
            return json.load(f)
    return []


def gecmis_kaydet(kullanici_adi, mesajlar):
    dosya = f"{kullanici_adi}.json"
    with open(dosya, "w") as f:
        json.dump(mesajlar, f)


if "user" not in st.session_state:
    st.title("Giriş Yap")
    with st.form("giris"):
        ad = st.text_input("Adınız:")
        btn = st.form_submit_button("Giriş")
    if btn and ad:
        st.session_state.user = ad
        kullanici_kaydet(ad)
        st.rerun()
else:
    ad = st.session_state.user
    st.sidebar.success(f"Kullanıcı: {ad}")

    if "OPENAI_API_KEY" not in st.secrets:
        st.error("Şifre Yok!")
        st.stop()

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    if "messages" not in st.session_state:
        st.session_state.messages = gecmis_yukle(ad)
        if not st.session_state.messages:
            st.session_state.messages = [
                {"role": "assistant", "content": "Merhaba!"}
            ]

    with st.sidebar:
        dosya = st.file_uploader("PDF Yükle", type="pdf")
        if dosya and "okundu" not in st.session_state:
            okuyucu = PyPDF2.PdfReader(dosya)
            metin = ""
            for sayfa in okuyucu.pages:
                metin += sayfa.extract_text()
            st.session_state.messages.insert(
                0,
                {"role": "system", "content": metin}
            )
            st.session_state.okundu = True
            gecmis_kaydet(ad, st.session_state.messages)
            st.success("PDF Okundu!")

    for msg in st.session_state.messages:
        if msg["role"] != "system":
            st.chat_message(msg["role"]).write(msg["content"])

    prompt = st.chat_input("Sorunuzu yazın...")

    if prompt:
        st.chat_message("user").write(prompt)
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )
        gecmis_kaydet(ad, st.session_state.messages)

        yanit = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        cevap = yanit.choices[0].message.content

        st.chat_message("assistant").write(cevap)
        st.session_state.messages.append(
            {"role": "assistant", "content": cevap}
        )
        gecmis_kaydet(ad, st.session_state.messages)
