import streamlit as st
from PyPDF2 import PdfReader
from gtts import gTTS
import tempfile
import os

# ---- SAYFA AYARI ----
st.set_page_config(
    page_title="Okuma Dostum",
    page_icon="📘",
    layout="centered"
)

# ---- STİL (ÖĞRENME GÜÇLÜĞÜNE UYGUN) ----
st.markdown("""
<style>
body {
    background-color: #f4f9ff;
}
.big-title {
    font-size: 40px;
    font-weight: bold;
    color: #2c3e50;
}
.card {
    background-color: #ffffff;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# ---- BAŞLIK ----
st.markdown('<div class="big-title">📘 Okuma Dostum</div>', unsafe_allow_html=True)
st.write("### Hoş geldin dostum 🌈")
st.write("Burada metinleri daha **kolay**, **anlaşılır** ve **eğlenceli** şekilde okuyacağız.")

# ---- PDF YÜKLEME ----
st.markdown('<div class="card">📄 <b>PDF Yükle</b></div>', unsafe_allow_html=True)
pdf_file = st.file_uploader("Bir PDF seç", type=["pdf"])

text = ""

if pdf_file:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        text += page.extract_text() + "\n"

    st.success("✅ PDF başarıyla yüklendi")

# ---- METİN GÖSTER ----
if text:
    st.markdown('<div class="card"><b>📖 Metin</b></div>', unsafe_allow_html=True)
    st.text_area("PDF içeriği", text, height=250)

    # ---- BUTONLAR ----
    col1, col2, col3 = st.columns(3)

    with col1:
        simplify = st.button("🅰️ Basitleştirerek Anlat")

    with col2:
        bullets = st.button("🅱️ Madde Madde Açıkla")

    with col3:
        speak = st.button("🔊 Seslendir")

    # ---- BASİTLEŞTİR ----
    if simplify:
        st.markdown('<div class="card">🅰️ <b>Basitleştirilmiş Anlatım</b></div>', unsafe_allow_html=True)
        st.write("Bu metin, ana fikirleri daha kolay anlaman için sadeleştirildi.")
        st.write(text[:500] + "...")

    # ---- MADDE MADDE ----
    if bullets:
        st.markdown('<div class="card">🅱️ <b>Madde Madde Açıklama</b></div>', unsafe_allow_html=True)
        sentences = text.split(".")[:5]
        for s in sentences:
            st.write("•", s.strip())

    # ---- SESLENDİRME (gTTS) ----
    if speak:
        tts = gTTS(text=text[:1000], lang="tr")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            audio_file = fp.name

        st.audio(audio_file)
