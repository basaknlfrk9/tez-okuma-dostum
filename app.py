st.write("GSHEETS OK")

import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from collections import Counter

# -------------------------------------------------
# SAYFA AYARI
# -------------------------------------------------
st.set_page_config(page_title="📚 Okuma Dostum", layout="wide")
st.title("📚 Okuma Dostum")

# -------------------------------------------------
# GOOGLE SHEETS BAĞLANTISI
# -------------------------------------------------
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope,
)
gc = gspread.authorize(credentials)

sheet = gc.open_by_key(
    st.secrets["connections"]["gsheets"]["spreadsheet_id"]
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
    records = sheet.get_all_records()
    df = pd.DataFrame(records)

    df = df[df["Kullanici"] == kullanici]
    df = df[df["Tip"].isin(["USER", "BOT"])]

    mesajlar = []
    for _, r in df.iterrows():
        role = "user" if r["Tip"] == "USER" else "assistant"
        mesajlar.append({"role": role, "content": r["Mesaj"]})

    return mesajlar

# -------------------------------------------------
# GİRİŞ EKRANI
# -------------------------------------------------
if "user" not in st.session_state:
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = gecmisi_yukle(isim)
        tabloya_yaz(isim, "SISTEM", "Giriş Yaptı")
        st.rerun()

# -------------------------------------------------
# ANA UYGULAMA
# -------------------------------------------------
else:
    st.sidebar.success(f"👤 {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        tabloya_yaz(st.session_state.user, "SISTEM", "Çıkış Yaptı")
        st.session_state.clear()
        st.rerun()

    # ---------------- PDF ----------------
    st.sidebar.header("📄 PDF Yükle")
    file = st.sidebar.file_uploader("PDF Yükle", type="pdf")

    pdf_text = ""
    if file:
        pdf = PyPDF2.PdfReader(file)
        for p in pdf.pages:
            pdf_text += p.extract_text() or ""

    # ---------------- CHAT ----------------
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if soru := st.chat_input("Sorunu yaz"):
        st.session_state.messages.append({"role": "user", "content": soru})
        tabloya_yaz(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            ek = f"PDF:\n{pdf_text[:1500]}\n\n" if pdf_text else ""
            yanit = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": ek + soru}]
            )
            cevap = yanit.choices[0].message.content
            st.write(cevap)

        st.session_state.messages.append({"role": "assistant", "content": cevap})
        tabloya_yaz(st.session_state.user, "BOT", cevap)

    # -------------------------------------------------
    # 📊 ANALİZ PANELİ
    # -------------------------------------------------
    st.divider()
    st.header("📊 Kullanım Analizi")

    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # En çok kullanılan kelimeler
    st.subheader("🔤 En Çok Kullanılan Kelimeler")
    user_msgs = df[df["Tip"] == "USER"]["Mesaj"]

    if len(user_msgs) > 0:
        kelimeler = " ".join(user_msgs).lower().split()
        sayim = Counter(kelimeler)
        st.write(sayim.most_common(10))
    else:
        st.info("Henüz kullanıcı mesajı yok.")

    # Giriş – çıkışlar
    st.subheader("⏱️ Giriş / Çıkış Kayıtları")
    st.dataframe(df[df["Tip"] == "SISTEM"])

    # -------------------------------------------------
    # 📥 CSV İNDİRME
    # -------------------------------------------------
    st.subheader("📥 Verileri İndir")

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📊 Tüm Logları CSV Olarak İndir",
        csv,
        "okuma_dostum_loglari.csv",
        "text/csv"
    )

