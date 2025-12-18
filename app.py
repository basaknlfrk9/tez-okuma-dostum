import streamlit as st
from openai import OpenAI
import PyPDF2
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ------------------ DOSYALAR ------------------
DATA_DIR = "data"
MESAJ_DOSYA = f"{DATA_DIR}/mesajlar.xlsx"
OTURUM_DOSYA = f"{DATA_DIR}/oturumlar.xlsx"

os.makedirs(DATA_DIR, exist_ok=True)

# ------------------ EXCEL OLUŞTUR ------------------
def excel_kontrol():
    if not os.path.exists(MESAJ_DOSYA):
        df = pd.DataFrame(columns=["Zaman", "Kullanici", "Tip", "Mesaj"])
        df.to_excel(MESAJ_DOSYA, index=False)

    if not os.path.exists(OTURUM_DOSYA):
        df = pd.DataFrame(columns=["Kullanici", "Giris", "Cikis", "Sure (dk)"])
        df.to_excel(OTURUM_DOSYA, index=False)

excel_kontrol()

# ------------------ MESAJ KAYDET ------------------
def mesaj_kaydet(kullanici, tip, mesaj):
    df = pd.read_excel(MESAJ_DOSYA)

    yeni = {
        "Zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "Kullanici": kullanici,
        "Tip": tip,
        "Mesaj": mesaj
    }

    df = pd.concat([df, pd.DataFrame([yeni])], ignore_index=True)
    df.to_excel(MESAJ_DOSYA, index=False)

# ------------------ GEÇMİŞİ YÜKLE ------------------
def gecmisi_yukle(kullanici):
    df = pd.read_excel(MESAJ_DOSYA)
    df = df[df["Kullanici"] == kullanici]
    df = df[df["Tip"].isin(["USER", "BOT"])]

    mesajlar = []
    for _, row in df.iterrows():
        mesajlar.append({
            "role": "user" if row["Tip"] == "USER" else "assistant",
            "content": row["Mesaj"]
        })
    return mesajlar

# ------------------ OTURUM KAYDI ------------------
def oturum_kaydet(kullanici, giris, cikis):
    df = pd.read_excel(OTURUM_DOSYA)

    sure = round((cikis - giris).total_seconds() / 60, 2)

    yeni = {
        "Kullanici": kullanici,
        "Giris": giris.strftime("%d/%m/%Y %H:%M:%S"),
        "Cikis": cikis.strftime("%d/%m/%Y %H:%M:%S"),
        "Sure (dk)": sure
    }

    df = pd.concat([df, pd.DataFrame([yeni])], ignore_index=True)
    df.to_excel(OTURUM_DOSYA, index=False)

# ------------------ GİRİŞ ------------------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.giris_zamani = datetime.now()
        st.session_state.messages = gecmisi_yukle(isim)

        mesaj_kaydet(isim, "SISTEM", "Giriş yaptı")
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    st.title("📚 Okuma Dostum")
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        cikis = datetime.now()
        oturum_kaydet(
            st.session_state.user,
            st.session_state.giris_zamani,
            cikis
        )

        mesaj_kaydet(st.session_state.user, "SISTEM", "Çıkış yaptı")
        st.session_state.clear()
        st.rerun()

    # PDF
    st.sidebar.header("📄 PDF Yükle")
    file = st.sidebar.file_uploader("PDF seç", type="pdf")

    pdf_icerik = ""
    if file:
        pdf = PyPDF2.PdfReader(file)
        for s in pdf.pages:
            pdf_icerik += s.extract_text() or ""
        st.sidebar.success("PDF okundu")

    # CHAT
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if soru := st.chat_input("Sorunu yaz"):
        st.session_state.messages.append({"role": "user", "content": soru})
        mesaj_kaydet(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            yanit = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": pdf_icerik[:1500] + "\n" + soru}]
            )
            cevap = yanit.choices[0].message.content
            st.write(cevap)

        st.session_state.messages.append({"role": "assistant", "content": cevap})
        mesaj_kaydet(st.session_state.user, "BOT", cevap)
