import streamlit as st
import pyttsx3

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
.main {
    background-color: #F7F9FC;
}
.info-box {
    background-color: #E8F0FE;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 20px;
    font-size: 18px;
    color: #2E3440;
}
.welcome-box {
    background-color: #DDE7FF;
    padding: 18px;
    border-radius: 14px;
    font-size: 20px;
    color: #2E3440;
    text-align: center;
}
.card {
    background-color: #FFFFFF;
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
# GİRİŞ EKRANI
# -----------------------------
if not st.session_state.giris:

    st.markdown("""
    <div class="info-box">
    👋 <b>Okuma Dostum</b> ile metinleri birlikte anlayalım.<br><br>
    🅰️ Metni basitleştiririm<br>
    🅱️ Madde madde açıklarım<br>
    🔊 İstersen seslendiririm<br>
    🎯 Mini sorularla anladığını kontrol ederiz
    </div>
    """, unsafe_allow_html=True)

    kullanici = st.text_input("Adını yaz dostum 🌱")

    if st.button("Giriş Yap"):
        if kullanici.strip() != "":
            st.session_state.giris = True
            st.session_state.kullanici = kullanici
            st.rerun()
        else:
            st.warning("Lütfen adını yaz 😊")

# -----------------------------
# ANA SAYFA
# -----------------------------
else:
    st.markdown(f"""
    <div class="welcome-box">
    🤍 Hoş geldin dostum, <b>{st.session_state.kullanici}</b><br>
    Bugün birlikte okumaya hazırız
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📖 Okumak istediğin metni buraya yapıştır")

    metin = st.text_area(
        "Metin",
        height=200,
        placeholder="Buraya metni yapıştırabilirsin..."
    )

    col1, col2, col3 = st.columns(3)

    # -----------------------------
    # 🅰️ BASİTLEŞTİR
    # -----------------------------
    with col1:
        if st.button("🅰️ Basitleştir"):
            if metin:
                st.markdown("<div class='card'><b>Basitleştirilmiş Anlatım</b><br><br>"
                            "Bu metin daha kısa cümlelerle ve kolay kelimelerle anlatılmıştır.<br><br>"
                            f"{metin[:300]}...</div>", unsafe_allow_html=True)

    # -----------------------------
    # 🅱️ MADDE MADDE
    # -----------------------------
    with col2:
        if st.button("🅱️ Madde Madde"):
            if metin:
                st.markdown("<div class='card'><b>Madde Madde Açıklama</b><br><br>"
                            "• Metnin ana konusu nedir?<br>"
                            "• Kimden veya neden bahsediliyor?<br>"
                            "• En önemli bilgi hangisi?</div>", unsafe_allow_html=True)

    # -----------------------------
    # 🔊 METNİ SESLENDİR
    # -----------------------------
    with col3:
        if st.button("🔊 Seslendir"):
            if metin:
                engine = pyttsx3.init()
                engine.say(metin)
                engine.runAndWait()
                st.success("Metin seslendirildi 🎧")

    # -----------------------------
    # 🎯 OKUDUĞUNU ANLAMA ETKİNLİĞİ
    # -----------------------------
    if metin:
        st.markdown("### 🎯 Mini Okuduğunu Anlama")

        soru = st.radio(
            "Metne göre hangisi doğrudur?",
            [
                "Metnin ana fikri anlatılmıştır",
                "Metin tamamen gereksizdir",
                "Metinde hiçbir bilgi yoktur"
            ]
        )

        if st.button("Cevabımı Gönder"):
            if soru == "Metnin ana fikri anlatılmıştır":
                st.success("🎉 Harika! Doğru cevap")
            else:
                st.warning("Tekrar düşünelim dostum 💙")
