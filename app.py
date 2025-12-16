import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Tez Asistanı", layout="wide")

st.title("🎓 Tez Okuma & Sohbet Asistanı")

# Şifre Kontrolü
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Lütfen API Anahtarınızı Secrets kısmına ekleyin.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Sohbet Geçmişini Hatırla
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Merhaba! Ben senin akademik asistanınım. Bana tezinde takıldığın yerleri sorabilirsin."
        }
    ]

# Eski Mesajları Ekrana Yaz
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Yeni Mesaj Girişi
if prompt := st.chat_input("Sorunuzu buraya yazın..."):
    # Senin mesajını ekle
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.write(prompt)

    # Cevap Üret
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages,
            stream=True,
        )
        response = st.write_stream(stream)

    # Cevabı kaydet
    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
