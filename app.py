import streamlit as st
import openai
import PyPDF2
from datetime import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ------------------ AYARLAR ------------------
st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.title("📚 Okuma Dostum")

# ------------------ OPENAI ------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ------------------ GOOGLE SHEETS ------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    st.secrets["GSHEETS"],
    scopes=scope
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_url(
    st.secrets["GSHEET_URL"]
).sheet1


def log_yaz(kullanici, tip, mesaj):
    sheet.append_row([
        datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        kullanici,
        tip,
        mesaj
    ])


# ------------------ GİRİŞ ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = []
        log_yaz(isim, "SİSTEM", "Giriş yaptı")
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    st.sidebar.success(f"Hoş geldin dostum 🌈 {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        log_yaz(st.session_state.user, "SİSTEM", "Çıkış yaptı")
        st.session_state.clear()
        st.rerun()

    # -------- PDF --------
    st.sidebar.header("📄 PDF Yükle")
    pdf_text = ""

    pdf_file = st.sidebar.file_uploader("PDF seç", type="pdf")
    if pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            pdf_text += page.extract_text() or ""

    # -------- METİN --------
    st.sidebar.header("📝 Metin Yapıştır")
    extra_text = st.sidebar.text_area("Metni buraya yapıştır")

    # -------- MODLAR --------
    st.sidebar.header("⚙️ Modlar")
    sade = st.sidebar.checkbox("🅰️ Basitleştirerek anlat")
    maddeler = st.sidebar.checkbox("🅱️ Madde madde açıkla")

    # -------- CHAT GEÇMİŞİ --------
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # -------- SORU --------
    if soru := st.chat_input("Sorunu yaz"):
        prompt = soru

        if sade:
            prompt = "Basit ve anlaşılır şekilde anlat: " + prompt
        if maddeler:
            prompt = "Madde madde açıkla: " + prompt
        if pdf_text:
            prompt = f"PDF içeriği:\n{pdf_text[:2000]}\n\nSoru: {prompt}"
        if extra_text:
            prompt = f"Metin:\n{extra_text[:2000]}\n\nSoru: {prompt}"

        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )
        log_yaz(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=st.session_state.messages
                )

                cevap = response.choices[0].message.content
                st.write(cevap)

                st.session_state.messages.append(
                    {"role": "assistant", "content": cevap}
                )
                log_yaz(st.session_state.user, "BOT", cevap)

            except Exception as e:
                st.error(f"Hata: {e}")
