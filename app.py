import streamlit as st
import pandas as pd
from datetime import datetime
from openai import OpenAI
import PyPDF2
import gspread
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# SAYFA
# --------------------------------------------------
st.set_page_config(page_title="📚 Okuma Dostum", layout="wide")

# --------------------------------------------------
# OPENAI
# --------------------------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --------------------------------------------------
# GOOGLE SHEETS MANUEL BAĞLANTI (KESİN ÇALIŞAN)
# --------------------------------------------------
creds_dict = st.secrets["connections"]["gsheets"]["credentials"]

credentials = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_url(
    st.secrets["connections"]["gsheets"]["spreadsheet"]
).sheet1

# --------------------------------------------------
# YARDIMCI FONKSİYONLAR
# --------------------------------------------------
def tabloya_yaz(kullanici, tip, mesaj):
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        kullanici,
        tip,
        mesaj
    ])

def gecmisi_yukle(kullanici):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        return []

    df = df[df["Kullanici"] == kullanici]
    df = df[df["Tip"].isin(["USER", "BOT"])]

    mesajlar = []
    for _, r in df.iterrows():
        role = "user" if r["Tip"] == "USER" else "assistant"
        mesajlar.append({"role": role, "content": r["Mesaj"]})
    return mesajlar

# --------------------------------------------------
# GİRİŞ
# --------------------------------------------------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")

    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.start_time = datetime.now()
        st.session_state.messages = gecmisi_yukle(isim)
        tabloya_yaz(isim, "SISTEM", "Giriş yaptı")
        st.rerun()

# --------------------------------------------------
# ANA
# --------------------------------------------------
else:
    st.sidebar.success(f"👋 Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        sure = (datetime.now() - st.session_state.start_time).seconds // 60
        tabloya_yaz(st.session_state.user, "SISTEM", f"Çıkış yaptı ({sure} dk)")
        st.session_state.clear()
        st.rerun()

    # PDF
    st.sidebar.header("📄 PDF Yükle")
    file = st.sidebar.file_uploader("PDF seç", type="pdf")
    pdf_text = ""

    if file:
        pdf = PyPDF2.PdfReader(file)
        for p in pdf.pages:
            pdf_text += p.extract_text() or ""

    # GEÇMİŞ
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # SORU
    if soru := st.chat_input("Sorunu yaz"):
        st.session_state.messages.append({"role": "user", "content": soru})
        tabloya_yaz(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            ek = f"PDF içeriği:\n{pdf_text[:1500]}\n\n" if pdf_text else ""
            yanit = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": ek + soru}]
            )
            cevap = yanit.choices[0].message.content
            st.write(cevap)

        st.session_state.messages.append(
            {"role": "assistant", "content": cevap}
        )
        tabloya_yaz(st.session_state.user, "BOT", cevap)
