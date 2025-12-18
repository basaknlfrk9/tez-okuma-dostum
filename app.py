import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from openai import OpenAI

st.set_page_config(page_title="Okuma Dostum")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Bağlantı ayarı hatalı!")

def kullanici_kaydet(ad):
    try:
        df = conn.read(ttl=0)
        yeni = pd.DataFrame([{
            "Kullanici Adi": ad,
            "Tarih": datetime.now().strftime("%d/%m/%Y %H:%M")
        }])
        df = pd.concat([df, yeni], ignore_index=True)
        conn.update(data=df)
    except:
        pass

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum'a Hoş Geldiniz")

    with st.form("giris"):
        isim = st.text_input("Adınız:")

        if st.form_submit_button("Giriş Yap") and isim:
            st.session_state.user = isim
            st.session_state.messages = []
            kullanici_kaydet(isim)
            st.rerun()

else:
    st.sidebar.write(f"Kullanıcı: {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap / Geçmişi Sil"):
        st.session_state.clear()
        st.rerun()

