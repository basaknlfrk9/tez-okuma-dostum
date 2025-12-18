import streamlit as st
from gtts import gTTS
import tempfile
import os

# -----------------------------
# SAYFA AYARLARI
# -----------------------------
st.set_page_config(
    page_title="Okuma Dostum",
    page_icon="📘",
    layout="centered"
)

# -----------------------------
# STİL (ÖÖG DOSTU)
# -----------------------------
st.markdown("""
<style>
.main {background-color: #F7F9FC;}
.info-box {
    background-color: #E8F0FE;
    padding: 20px;
    border-radius: 16px;
    font-size: 18px;
}
.welcome-box {
    background-color: #DDE7FF;
    padding: 18px;
    border-radius: 14px;
    font-size: 20px;
    text-align: center;
}
.card {
    background-color: white;
    padding: 20px;
    border-radius: 16px;
    margin-top: 15px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SESSION STATE
# -----------------------------
if "giris" not in st.session_state:
    st.session_state.giris = False

# -----------------------------
# BAŞLIK
# -----------------------------
st.title("📘 Okuma Dostum")

# -----------------------------
# GİRİŞ
# -----------------------------
if not st.session_state.giris:
    st.markdown("""
    <div class="info-box">
    👋 <b>Okuma Dostum</b> ile metinleri birlikte anlayalım.<br><br>
    🅰️ Basitleştirerek anlatır<br>
    🅱️ Madde madde açıklar<br>
    🔊 Metni seslendirir<br>
    🎯 Mini sorularla kontrol eder
    </div>
    """, unsafe_allow_html=True)

    ad = st.text_input("Adını yaz dostum 🌱")

    if st.button("Giriş Yap"):
        if ad.strip():
            st.session_state.giris = True
            st.session_state.ad = ad
            st.rerun()
        else:
            st.warning("Adını yazmalısın 😊")

# -----------------------------
# ANA SAYFA
# -----------------------------
else:
    st.markdown(f"""
    <div class="welcome-box">
    🤍 Hoş geldin dostum, <b>{st.session_state.ad}</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📖 Metni buraya yapıştır")

    metin = st.text_area(
        "Metin",
        height=200,
        placeholder="Okumak istediğin metni buraya yazabilirsin..."
    )

    col1, col2, col3 = st.columns(3)

    # 🅰️ Basitleştir
    with col1:
        if st.button("🅰️ Basitleştir") and metin:
            st.markdown(
                f"<div class='card'><b>Basitleştirilmiş Anlatım</b><br><br>{metin[:250]}...</div>",
                unsafe_allow_html=True
            )

    # 🅱️ Madde Madde
    with col2:
        if st.button("🅱️ Madde Madde") and metin:
            st.markdown("""
            <div class='card'>
            <b>Madde Madde Açıklama</b><br><br>
            • Metnin konusu nedir?<br>
            • En önemli bilgi hangisi?<br>
            • Kim veya ne anlatılıyor?
            </div>
            """, unsafe_allow_html=True)

    # 🔊 TTS
    with col3:
        if st.button("🔊 Seslendir") and metin:
            tts = gTTS(text=metin, lang="tr")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts.save(fp.name)
                st.audio(fp.name)

    # 🎯 Mini Etkinlik
    if metin:
        st.markdown("### 🎯 Mini Okuduğunu Anlama")

        cevap = st.radio(
            "Metne göre hangisi doğrudur?",
            [
                "Metnin ana fikri vardır",
                "Metin anlamsızdır",
                "Metinde bilgi yoktur"
            ]
        )

        if st.button("Cevabı Gönder"):
            if cevap == "Metnin ana fikri vardır":
                st.success("🎉 Harika dostum!")
            else:
                st.warning("Bir daha bakalım 💙")
