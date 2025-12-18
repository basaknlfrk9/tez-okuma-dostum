import streamlit as st
from openai import OpenAI
import PyPDF2
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ------------------ GOOGLE SHEETS ------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# --------- MESAJ TABLOSUNA YAZ ---------
def tabloya_yaz(kullanici, mesaj_tipi, icerik):
    try:
        df = conn.read(worksheet="mesajlar", ttl=0)

        yeni = pd.DataFrame([{
            "Zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Kullanici": kullanici,
            "Tip": mesaj_tipi,
            "Mesaj": icerik
        }])

        df = pd.concat([df, yeni], ignore_index=True)
        conn.update(worksheet="mesajlar", data=df)
    except:
        pass

# --------- ESKİ SOHBETLERİ YÜKLE ---------
def gecmisi_yukle(kullanici):
    try:
        df = conn.read(worksheet="mesajlar", ttl=0)
        df = df[df["Kullanici"] == kullanici]
        df = df[df["Tip"].str.upper().isin(["USER", "BOT"])]

        mesajlar = []
        for _, row in df.iterrows():
            role = "user" if row["Tip"] == "USER" else "assistant"
            mesajlar.append({
                "role": role,
                "content": row["Mesaj"]
            })
        return mesajlar
    except:
        return []

# --------- OTURUM KAYDI (SÜRE) ---------
def oturum_kaydet(kullanici, giris, cikis):
    try:
        df = conn.read(worksheet="oturumlar", ttl=0)

        sure = round((cikis - giris).total_seconds() / 60, 2)

        yeni = pd.DataFrame([{
            "Kullanici": kullanici,
            "Giris": giris.strftime("%d/%m/%Y %H:%M:%S"),
            "Cikis": cikis.strftime("%d/%m/%Y %H:%M:%S"),
            "Sure (dk)": sure
        }])

        df = pd.concat([df, yeni], ignore_index=True)
        conn.update(worksheet="oturumlar", data=df)
    except:
        pass

# ------------------ GİRİŞ EKRANI ------------------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.giris_zamani = datetime.now()
        st.session_state.messages = gecmisi_yukle(isim)

        tabloya_yaz(isim, "SİSTEM", "Giriş Yaptı")
        st.rerun()

# ------------------ ANA UYGULAMA ------------------
else:
    st.title("📚 Okuma Dostum")
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    # -------- ÇIKIŞ --------
    if st.sidebar.button("Çıkış Yap"):
        cikis = datetime.now()
        giris = st.session_state.giris_zamani

        oturum_kaydet(st.session_state.user, giris, cikis)
        tabloya_yaz(st.session_state.user, "SİSTEM", "Çıkış Yaptı")

        st.session_state.clear()
        st.rerun()

    # -------- PDF YÜKLEME --------
    st.sidebar.header("📄 PDF Yükleme")
    file = st.sidebar.file_uploader("PDF Yükleyin", type="pdf")

    pdf_icerik = ""
    if file:
        pdf = PyPDF2.PdfReader(file)
        for sayfa in pdf.pages:
            pdf_icerik += sayfa.extract_text() or ""
        st.sidebar.success("PDF Okundu")

    # -------- CHATBOT --------
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OPENAI_API_KEY tanımlı değil")
    else:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        # Eski mesajları göster
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        # Yeni soru
        if soru := st.chat_input("Sorunu buraya yaz..."):
            st.session_state.messages.append({"role": "user", "content": soru})
            tabloya_yaz(st.session_state.user, "USER", soru)

            with st.chat_message("assistant"):
                ek = f"PDF İçeriği:\n{pdf_icerik[:1500]}\n\n" if pdf_icerik else ""
                yanit = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": ek + soru}]
                )
                cevap = yanit.choices[0].message.content
                st.write(cevap)

            st.session_state.messages.append({"role": "assistant", "content": cevap})
            tabloya_yaz(st.session_state.user, "BOT", cevap)

