import streamlit as st
import pandas as pd
from datetime import datetime
from openai import OpenAI
import PyPDF2
import requests
import io

st.set_page_config(page_title="📚 Okuma Dostum", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1GJCUPsYNPhhPasd6me4fUxO8AlSqW7DxWiPsmWKgNUo/export?format=csv"

def kaydet(kullanici, tip, mesaj):
    try:
        df = pd.read_csv(SHEET_CSV_URL)
    except:
        df = pd.DataFrame(columns=["Zaman", "Kullanici", "Tip", "Mesaj"])

    yeni = {
        "Zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Kullanici": kullanici,
        "Tip": tip,
        "Mesaj": mesaj
    }

    df = pd.concat([df, pd.DataFrame([yeni])], ignore_index=True)

    # CSV'yi tekrar Google Sheets'e yazmak mümkün değil
    # ama KAYIT GELDİĞİNİ GÖRMEK için bu yeterli
    df.to_csv("/tmp/log.csv", index=False)

def gecmisi_yukle(kullanici):
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        df = df[df["Kullanici"] == kullanici]
        return [
            {"role": "user" if r["Tip"] == "USER" else "assistant", "content": r["Mesaj"]}
            for _, r in df.iterrows()
            if r["Tip"] in ["USER", "BOT"]
        ]
    except:
        return []

# ---------------- GİRİŞ ----------------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = gecmisi_yukle(isim)
        kaydet(isim, "SISTEM", "Giriş Yaptı")
        st.rerun()

# ---------------- ANA ----------------
else:
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        kaydet(st.session_state.user, "SISTEM", "Çıkış Yaptı")
        st.session_state.clear()
        st.rerun()

    st.sidebar.header("📄 PDF Yükle")
    pdf = st.sidebar.file_uploader("PDF seç", type="pdf")

    pdf_text = ""
    if pdf:
        reader = PyPDF2.PdfReader(pdf)
        for p in reader.pages:
            pdf_text += p.extract_text() or ""

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if soru := st.chat_input("Sorunu yaz"):
        st.session_state.messages.append({"role": "user", "content": soru})
        kaydet(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            yanit = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": pdf_text[:1500] + "\n\n" + soru}]
            )
            cevap = yanit.choices[0].message.content
            st.write(cevap)

        st.session_state.messages.append({"role": "assistant", "content": cevap})
        kaydet(st.session_state.user, "BOT", cevap)
