import streamlit as st
from openai import OpenAI
import PyPDF2
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Okuma Dostum", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

def tabloya_yaz(kullanici, mesaj_tipi, icerik):
    try:
        df = conn.read(ttl=0)
        yeni_veri = pd.DataFrame([{
            "Zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Kullanici": kullanici,
            "Tip": mesaj_tipi,
            "Mesaj": icerik
        }])
        df = pd.concat([df, yeni_veri], ignore_index=True)
        conn.update(data=df)
    except:
        pass

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = []
        tabloya_yaz(isim, "SİSTEM", "Giriş Yaptı")
        st.rerun()

else:
    st.title("📚 Okuma Dostum")
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        tabloya_yaz(st.session_state.user, "SİSTEM", "Çıkış Yaptı")
        st.session_state.clear()
        st.rerun()
