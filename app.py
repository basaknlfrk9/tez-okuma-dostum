import streamlit as st

st.set_page_config(page_title="Kurulum Kontrol")
st.title("Sorun Tespiti")

st.info("Sistem parcalari kontrol ediliyor...")

try:
    import openai
    st.success("1. OpenAI Kutuphanesi: YUKLU")
except ImportError:
    st.error("1. OpenAI Kutuphanesi: EKSIK! (requirements dosyasina bak)")

try:
    import PyPDF2
    st.success("2. PyPDF2 Kutuphanesi: YUKLU")
except ImportError:
    st.error("2. PyPDF2 Kutuphanesi: EKSIK! (requirements dosyasina PyPDF2 ekle)")

if "OPENAI_API_KEY" in st.secrets:
    st.success("3. API Sifresi: MEVCUT")
else:
    st.error("3. API Sifresi: YOK")

st.write("---")
st.warning("Eger yukarida KIRMIZI bir kutu varsa, o sorunu cozmemiz lazim.")
