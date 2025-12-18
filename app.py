import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from datetime import datetime

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Tez Okuma Dostum",
    page_icon="📘",
    layout="centered"
)

st.title("📘 Tez Okuma Dostum")

# -------------------------------------------------
# OPENAI CLIENT
# -------------------------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------------------------------------
# GOOGLE SHEETS BAĞLANTISI (STABLE YÖNTEM)
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
    kullanici_adi = st.text_input("👤 Kullanıcı adını gir")

    if st.button("Giriş Yap") and kullanici_adi.strip() != "":
        st.session_state.kullanici = kullanici_adi
        st.session_state.messages = gecmisi_yukle(kullanici_adi)
        st.rerun()

    st.stop()

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
    # kullanıcı mesajı
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    tabloya_yaz(st.session_state.kullanici, "USER", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    # openai cevap
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state.messages
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
