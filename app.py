import streamlit as st
from openai import OpenAI
import PyPDF2
from datetime import datetime
import json
import os

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ---------- LOG AYARLARI ----------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def log_yaz(kullanici, tip, mesaj):
    dosya = f"{LOG_DIR}/{kullanici}.json"

    if os.path.exists(dosya):
        with open(dosya, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append({
        "zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "tip": tip,
        "mesaj": mesaj
    })

    with open(dosya, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def gecmisi_yukle(kullanici):
    dosya = f"{LOG_DIR}/{kullanici}.json"
    if not os.path.exists(dosya):
        return []

    with open(dosya, "r", encoding="utf-8") as f:
        data = json.load(f)

    mesajlar = []
    for d in data:
        if d["tip"] == "USER":
            mesajlar.append({"role": "user", "content": d["mesaj"]})
        elif d["tip"] == "BOT":
            mesajlar.append({"role": "assistant", "content": d["mesaj"]})

    return mesajlar

# ---------- GİRİŞ ----------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = gecmisi_yukle(isim)
        log_yaz(isim, "SİSTEM", "Giriş yaptı")
        st.rerun()

# ---------- ANA SAYFA ----------
else:
    st.title("📚 Okuma Dostum")
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        log_yaz(st.session_state.user, "SİSTEM", "Çıkış yaptı")
        st.session_state.clear()
        st.rerun()

    # PDF YÜKLEME
    st.sidebar.header("📄 PDF Yükle")
    file = st.sidebar.file_uploader("PDF seç", type="pdf")

    pdf_icerik = ""
    if file:
        pdf = PyPDF2.PdfReader(file)
        for sayfa in pdf.pages:
            pdf_icerik += sayfa.extract_text() or ""
        st.sidebar.success("PDF okundu")

    # CHATBOT
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OPENAI_API_KEY eksik")
    else:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        if soru := st.chat_input("Sorunu yaz..."):
            st.session_state.messages.append({"role": "user", "content": soru})
            log_yaz(st.session_state.user, "USER", soru)

            with st.chat_message("assistant"):
                ek = f"PDF İçeriği:\n{pdf_icerik[:1500]}\n\n" if pdf_icerik else ""
                yanit = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": ek + soru}]
                )
                cevap = yanit.choices[0].message.content
                st.write(cevap)

            st.session_state.messages.append({"role": "assistant", "content": cevap})
            log_yaz(st.session_state.user, "BOT", cevap)
