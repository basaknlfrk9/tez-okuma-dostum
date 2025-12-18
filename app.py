import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime
import PyPDF2

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Okuma Dostum",
    page_icon="📘",
    layout="wide"
)

st.title("📘 Okuma Dostum")

# -------------------------------------------------
# OPENAI
# -------------------------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------------------------------------
# GOOGLE SHEETS BAĞLANTISI
# -------------------------------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    st.secrets["gsheets"],
    scopes=scope
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(
    st.secrets["SPREADSHEET_ID"]
).sheet1

# -------------------------------------------------
# YARDIMCI FONKSİYONLAR
# -------------------------------------------------
def tabloya_yaz(kullanici, tip, mesaj):
    sheet.append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        kullanici,
        tip,
        mesaj
    ])

def gecmisi_yukle(kullanici):
    rows = sheet.get_all_records()
    mesajlar = []

    for r in rows:
        if r["Kullanici"] == kullanici and r["Tip"] in ["USER", "BOT"]:
            mesajlar.append({
                "role": "user" if r["Tip"] == "USER" else "assistant",
                "content": r["Mesaj"]
            })
    return mesajlar

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
if "kullanici" not in st.session_state:
    st.session_state.kullanici = ""

if st.session_state.kullanici == "":
    isim = st.text_input("👤 Adını yaz")

    if st.button("Giriş Yap") and isim.strip():
        st.session_state.kullanici = isim
        st.session_state.messages = gecmisi_yukle(isim)
        st.rerun()

    st.stop()

# 👋 GİRİŞ SONRASI MESAJ
st.success(f"🤍 Hoş geldin dostum, {st.session_state.kullanici}")

# -------------------------------------------------
# SIDEBAR – PDF
# -------------------------------------------------
st.sidebar.header("📄 PDF Yükle")
pdf_file = st.sidebar.file_uploader(
    "PDF dosyası seç",
    type=["pdf"]
)

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

if pdf_file:
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""

    st.session_state.pdf_text = text
    st.sidebar.success("PDF yüklendi")

# -------------------------------------------------
# CHAT GEÇMİŞİ
# -------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = gecmisi_yukle(st.session_state.kullanici)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------------------------
# CHAT INPUT
# -------------------------------------------------
prompt = st.chat_input("Sorunu yaz...")

if prompt:
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    tabloya_yaz(st.session_state.kullanici, "USER", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    context = ""
    if st.session_state.pdf_text:
        context = (
            "Aşağıdaki metin bir PDF içeriğidir. "
            "Soruyu yanıtlarken bu içeriği dikkate al:\n\n"
            + st.session_state.pdf_text[:4000]
        )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": context},
            *st.session_state.messages
        ]
    )

    cevap = response.choices[0].message.content

    st.session_state.messages.append({
        "role": "assistant",
        "content": cevap
    })

    tabloya_yaz(st.session_state.kullanici, "BOT", cevap)

    with st.chat_message("assistant"):
        st.markdown(cevap)

# -------------------------------------------------
# ÇIKIŞ
# -------------------------------------------------
st.divider()
if st.button("🚪 Çıkış Yap"):
    st.session_state.clear()
    st.rerun()
