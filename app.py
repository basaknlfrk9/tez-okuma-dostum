import streamlit as st
from openai import OpenAI
import PyPDF2
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="📚 Okuma Dostum", layout="wide")

# ---------------- GOOGLE SHEETS BAĞLANTISI ----------------
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------- KAYIT FONKSİYONU ----------------
def kaydet(kullanici, tip, mesaj):
    try:
        df = conn.read(ttl=0)
    except:
        df = pd.DataFrame(columns=["Zaman", "Kullanici", "Tip", "Mesaj"])

    yeni = pd.DataFrame([{
        "Zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Kullanici": kullanici,
        "Tip": tip,
        "Mesaj": mesaj
    }])

    df = pd.concat([df, yeni], ignore_index=True)
    conn.update(data=df)

# ---------------- GEÇMİŞ YÜKLE ----------------
def gecmisi_yukle(kullanici):
    try:
        df = conn.read(ttl=0)
        df = df[df["Kullanici"] == kullanici]
        df = df[df["Tip"].isin(["USER", "BOT"])]

        mesajlar = []
        for _, r in df.iterrows():
            mesajlar.append({
                "role": "user" if r["Tip"] == "USER" else "assistant",
                "content": r["Mesaj"]
            })
        return mesajlar
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

    # PDF
    st.sidebar.header("📄 PDF Yükle")
    pdf = st.sidebar.file_uploader("PDF seç", type="pdf")

    pdf_text = ""
    if pdf:
        reader = PyPDF2.PdfReader(pdf)
        for p in reader.pages:
            pdf_text += p.extract_text() or ""

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    # Eski mesajları göster
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # Yeni mesaj
    if soru := st.chat_input("Sorunu yaz"):
        st.session_state.messages.append({"role": "user", "content": soru})
        kaydet(st.session_state.user, "USER", soru)

        with st.chat_message("assistant"):
            yanit = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": pdf_text[:1500] + "\n\n" + soru
                }]
            )
            cevap = yanit.choices[0].message.content
            st.write(cevap)

        st.session_state.messages.append(
            {"role": "assistant", "content": cevap}
        )
        kaydet(st.session_state.user, "BOT", cevap)
