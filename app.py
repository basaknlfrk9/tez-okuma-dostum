import streamlit as st
import requests

st.set_page_config(page_title="Bağlantı Kontrolü")

st.title("İnternet ve Sunucu Testi")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Şifre Yok!")
    st.stop()

st.write("---")

st.info("1. Google Test Ediliyor...")

try:
    response = requests.get("https://www.google.com", timeout=5)
    if response.status_code == 200:
        st.success("Google BAŞARILI (İnternet Var)")
    else:
        st.error("Google HATA Verdi")
except Exception as e:
    st.error(f"Google Bağlanamadı: {e}")

st.write("---")

st.info("2. OpenAI Test Ediliyor...")

try:
    headers = {"Authorization": f"Bearer {st.secrets['OPENAI_API_KEY']}"}
    response = requests.get(
        "https://api.openai.com/v1/models",
        headers=headers,
        timeout=10
    )
    if response.status_code == 200:
        st.balloons()
        st.success("OpenAI BAŞARILI! (Sunucu Açık)")
        st.write("HATA YOK. Her şey çalışıyor.")
    else:
        st.error(f"OpenAI Cevap Verdi ama HATA KODU: {response.status_code}")
        st.json(response.json())
except Exception as e:
    st.error(f"OpenAI Bağlantısı KOPTU: {e}")
