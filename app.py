import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
from io import BytesIO
import tempfile
import re

# =====================================================
# SAYFA AYARI
# =====================================================
st.set_page_config(
    page_title="Okuma Dostum",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# ÖÖG DOSTU CSS (BÜYÜK PUNTO + BOŞLUK)
# =====================================================
st.markdown("""
<style>
html, body, [class*="css"] {
    font-size: 20px !important;
}
p, div, span {
    line-height: 1.9 !important;
}
.stChatMessage p {
    font-size: 20px !important;
}
.stTextArea textarea {
    font-size: 20px !important;
    line-height: 1.9 !important;
}
.stButton button {
    font-size: 18px !important;
    padding: 10px 16px !important;
    border-radius: 16px !important;
}
.block-container {
    padding-top: 2rem;
    max-width: none;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# OPENAI
# =====================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =====================================================
# TTS (NOKTALAMA OKUMASIN DİYE)
# =====================================================
def temizle_tts(metin):
    metin = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()

def seslendir(metin):
    metin = temizle_tts(metin)
    tts = gTTS(metin, lang="tr")
    buf = BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()

# =====================================================
# GİRİŞ EKRANI
# =====================================================
if "user" not in st.session_state:
    st.markdown("""
    <div style="text-align:center; margin-top:60px;">
        <div style="font-size:52px; font-weight:900;">📚 Okuma Dostum</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-top:30px;">
        <div style="font-size:30px;">👋</div>
        <div style="font-size:26px; font-weight:800;">Hoş geldiniz</div>
    </div>
    """, unsafe_allow_html=True)

    isim = st.text_input("Adını yaz")

    if st.button("Giriş Yap") and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.messages = []
        st.session_state.last_bot_text = ""
        st.rerun()

    with st.expander("❓ Chatbot nasıl kullanılır?"):
        st.markdown("""
- Öğretmen metni verir (PDF ya da yazı)
- Sen metni benimle okursun
- Ana fikri birlikte buluruz
- Soruları çözeriz
- İstersen 🎤 ile sor, 🔊 ile dinle
""")
    st.stop()

# =====================================================
# ÜST BAŞLIK (TEK ODAK – KESİN GÖRÜNÜR)
# =====================================================
st.markdown(f"""
<div style="text-align:center; margin-bottom:10px;">
    <div style="font-size:44px; font-weight:900;">📚 Okuma Dostum</div>
    <div style="font-size:18px; opacity:0.7;">{st.session_state.user}</div>
</div>
""", unsafe_allow_html=True)

col_exit = st.columns([8,2])[1]
with col_exit:
    if st.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")

# =====================================================
# SOL PANEL (SADE)
# =====================================================
with st.sidebar:
    with st.expander("📄 PDF ekle"):
        pdf_file = st.file_uploader("PDF seç", type="pdf")
        if pdf_file:
            reader = PdfReader(pdf_file)
            text = ""
            for p in reader.pages:
                if p.extract_text():
                    text += p.extract_text()
            st.session_state.pdf_text = text

    with st.expander("📝 Metin ekle"):
        st.session_state.extra_text = st.text_area("Metni buraya yapıştır", height=200)

pdf_text = st.session_state.get("pdf_text", "")
extra_text = st.session_state.get("extra_text", "")

# =====================================================
# SOHBET GEÇMİŞİ
# =====================================================
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# =====================================================
# ALT GİRİŞ ALANI (ANA ODAK)
# =====================================================
c_msg, c_mic, c_audio, c_send = st.columns([8,1,1,2])

with c_msg:
    soru = st.text_area(
        "",
        placeholder="Sorunu yaz (ör: Bu metnin ana fikrini bulalım)",
        height=70
    )

with c_mic:
    audio = audio_recorder("🎤", key="mic")

    if audio:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(audio)
            with open(f.name, "rb") as a:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=a,
                    language="tr"
                )
        soru = transcript.text

with c_audio:
    if st.button("🔊"):
        if st.session_state.last_bot_text:
            st.audio(seslendir(st.session_state.last_bot_text), format="audio/mp3")

with c_send:
    if st.button("Gönder") and soru.strip():
        st.session_state.messages.append({"role":"user","content":soru})

        kaynak = pdf_text or extra_text or "Kısa bir metinle ana fikir çalışması yap."
        prompt = f"""
Sen özel öğrenme güçlüğü olan bir öğrenciyle çalışan yardımcı öğretmensin.
Sunuş yoluyla öğretim kullan.
Metni kısaca açıkla, örnek ver, ana fikri sor.

METİN:
{kaynak}

SORU:
{soru}
"""
        yanit = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        ).choices[0].message.content

        st.session_state.messages.append({"role":"assistant","content":yanit})
        st.session_state.last_bot_text = yanit
        st.rerun()
