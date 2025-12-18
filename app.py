import streamlit as st
from PyPDF2 import PdfReader
from gtts import gTTS
import tempfile

# ---------------- SAYFA AYARI ----------------
st.set_page_config(
    page_title="Okuma Dostum",
    page_icon="📘",
    layout="wide"
)

# ---------------- STİL ----------------
st.markdown("""
<style>
body { background-color: #f4f9ff; }
.big-title { font-size: 42px; font-weight: bold; color: #2c3e50; }
.card {
    background-color: #ffffff;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================== GİRİŞ SAYFASI ==================
if not st.session_state.logged_in:
    st.markdown('<div class="big-title">📘 Okuma Dostum</div>', unsafe_allow_html=True)
    st.write("### Hoş geldin dostum 🌈")
    st.write("Devam etmek için giriş yap")

    with st.form("login_form"):
        username = st.text_input("👤 Kullanıcı Adı")
        password = st.text_input("🔑 Şifre", type="password")
        login_btn = st.form_submit_button("Giriş Yap")

    if login_btn:
        if username and password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Lütfen kullanıcı adı ve şifre gir")

# ================== ANA UYGULAMA ==================
else:
    # --------- YAN PANEL ---------
    st.sidebar.markdown("## 📂 İçerik Yükleme")

    pdf_file = st.sidebar.file_uploader(
        "📄 PDF Yükle",
        type=["pdf"]
    )

    pasted_text = st.sidebar.text_area(
        "📝 Metin Yapıştır",
        height=200,
        placeholder="Buraya metni yapıştırabilirsin..."
    )

    # --------- PDF OKUMA ---------
    text = ""
    if pdf_file:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"

    if pasted_text:
        text += pasted_text

    # --------- ANA EKRAN ---------
    st.markdown(f'<div class="big-title">Hoş geldin {st.session_state.username} 🌟</div>', unsafe_allow_html=True)
    st.write("### Okuma Dostun seninle 📘")

    if not text:
        st.info("👈 Soldan PDF yükle veya metin yapıştır")
    else:
        st.markdown('<div class="card"><b>📖 Metin</b></div>', unsafe_allow_html=True)
        st.text_area("İçerik", text, height=300)

        # --------- BUTONLAR ---------
        col1, col2, col3 = st.columns(3)

        with col1:
            simplify = st.button("🅰️ Basitleştirerek Anlat")

        with col2:
            bullets = st.button("🅱️ Madde Madde Açıkla")

        with col3:
            speak = st.button("🔊 Seslendir")

        # --------- BASİTLEŞTİR ---------
        if simplify:
            st.markdown('<div class="card">🅰️ Basitleştirilmiş Anlatım</div>', unsafe_allow_html=True)
            st.write("Bu metnin ana fikri sadeleştirilmiştir:")
            st.write(text[:500] + "...")

        # --------- MADDE MADDE ---------
        if bullets:
            st.markdown('<div class="card">🅱️ Madde Madde Açıklama</div>', unsafe_allow_html=True)
            for s in text.split(".")[:6]:
                if s.strip():
                    st.write("•", s.strip())

        # --------- SESLENDİRME ---------
        if speak:
            tts = gTTS(text=text[:1200], lang="tr")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts.save(fp.name)
                st.audio(fp.name)

        # --------- SORU SOR ---------
        st.markdown('<div class="card"><b>❓ Metinle İlgili Soru Sor</b></div>', unsafe_allow_html=True)
        question = st.text_input("Sorunu yaz")

        if question:
            st.write("🤖 Bu özellik yakında daha akıllı hale gelecek.")
            st.write("Sorduğun soru:", question)

    # --------- ÇIKIŞ ---------
    if st.sidebar.button("🚪 Çıkış Yap"):
        st.session_state.logged_in = False
        st.rerun()
