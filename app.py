import streamlit as st
from openai import OpenAI
import PyPDF2

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.title("📚 Okuma Dostum")

# ------------------ GİRİŞ KONTROLÜ ------------------
if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    isim = st.text_input("Adınızı yazın:")

    if st.button("Giriş Yap") and isim:
        st.session_state.user = isim
        st.session_state.messages = []
        st.rerun()

else:
    st.sidebar.success(f"Hoş geldin {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

    # ------------------ PDF YÜKLEME ------------------
    st.header("📄 Dosya Analizi ve Sohbet")
    file = st.file_uploader("PDF Yükleyin", type="pdf")

    icerik = ""
    if file:
        pdf = PyPDF2.PdfReader(file)
        for sayfa in pdf.pages:
            icerik += sayfa.extract_text() or ""
        st.info("PDF Okundu!")

    # ------------------ CHATBOT ------------------
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OPENAI_API_KEY secrets içinde tanımlı değil")
    else:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        if soru := st.chat_input("Sorunuzu yazın..."):
            st.session_state.messages.append({"role": "user", "content": soru})

            with st.chat_message("user"):
                st.write(soru)

            with st.chat_message("assistant"):
                ek_bilgi = f"PDF İçeriği:\n{icerik[:1500]}\n\n" if icerik else ""
                yanit = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Bir okuma asistanısın."},
                        {"role": "user", "content": ek_bilgi + soru}
                    ]
                )
                cevap = yanit.choices[0].message.content
                st.write(cevap)

            st.session_state.messages.append({"role": "assistant", "content": cevap})
