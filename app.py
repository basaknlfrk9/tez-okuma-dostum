import streamlit as st
from openai import OpenAI
import json, time, random
from io import BytesIO
from gtts import gTTS

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# =========================
# STYLE (SADE)
# =========================
st.markdown("""
<style>
html, body {font-size:18px;}
.stButton button {
    height:2.8em;
    border-radius:12px;
    font-weight:700;
}
.card {
    background:#fff;
    padding:15px;
    border-radius:12px;
    margin-bottom:10px;
}
.highlight {
    background:#fff8e1;
    padding:20px;
    border-radius:15px;
    font-size:20px;
}
</style>
""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =========================
# 🔥 ÖÖG UYUMLU PROMPTLAR
# =========================

def generate_ai_hint(metin, soru, secim, level=1):

    system_prompt = """
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine yardım eden bir öğretmensin.

Kurallar:
- Çok basit konuş
- En fazla 2 cümle yaz
- Cevabı ASLA söyleme
- Öğrenciyi metne yönlendir
- Motive edici ol
"""

    user_prompt = f"""
Metin: {metin[:1000]}

Soru: {soru['kok']}
Öğrencinin seçimi: {secim}

İpucu ver.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":user_prompt}
        ]
    )

    return resp.choices[0].message.content


def explain_word(word):

    system_prompt = """
Sen çocuklara kelime öğreten bir öğretmensin.

Kurallar:
- Çok basit anlat
- 1-2 cümle
- Örnek ver
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":f"{word} kelimesini açıkla"}
        ]
    )

    return resp.choices[0].message.content


# =========================
# STATE
# =========================

if "phase" not in st.session_state:
    st.session_state.phase = "start"

if "q_idx" not in st.session_state:
    st.session_state.q_idx = 0

if "hints" not in st.session_state:
    st.session_state.hints = 0

if "correct" not in st.session_state:
    st.session_state.correct = 0


# =========================
# SAMPLE DATA
# =========================

metin = """Bobo ormanda yürüyordu. Bir kuş gördü. Kuş çok üzgündü çünkü yuvası yıkılmıştı."""

sorular = [
    {
        "kok":"Bobo'nun gördüğü kuş ne yapıyordu?",
        "A":"Yemek yiyordu",
        "B":"Oyun oynuyordu",
        "C":"Üzgündü",
        "dogru":"C"
    }
]

# =========================
# START
# =========================

if st.session_state.phase == "start":

    st.title("Okuma Dostum")

    if st.button("Başla"):
        st.session_state.phase = "read"
        st.rerun()

# =========================
# READ
# =========================

elif st.session_state.phase == "read":

    st.subheader("Metni Oku")

    st.markdown(f"<div class='highlight'>{metin}</div>", unsafe_allow_html=True)

    if st.button("Devam"):
        st.session_state.phase = "questions"
        st.rerun()

# =========================
# QUESTIONS
# =========================

elif st.session_state.phase == "questions":

    i = st.session_state.q_idx
    q = sorular[i]

    st.subheader(f"Soru {i+1}")

    st.markdown(f"<div class='card'><b>{q['kok']}</b></div>", unsafe_allow_html=True)

    # 🔥 BOŞ GELEN SEÇENEK
    secim = st.radio(
        "Cevap",
        ["A","B","C"],
        index=None,
        format_func=lambda x: f"{x}) {q[x]}"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cevapla"):

            if secim is None:
                st.warning("Seçim yap")
                st.stop()

            if secim == q["dogru"]:
                st.success("Doğru 🎉")
                st.session_state.correct += 1
                st.session_state.phase = "finish"
                st.rerun()
            else:
                st.error("Yanlış")

                st.session_state.hints += 1
                hint = generate_ai_hint(metin, q, secim)

                st.info(hint)

    with col2:
        if st.button("Geç"):
            st.session_state.phase = "finish"
            st.rerun()

# =========================
# FINISH
# =========================

elif st.session_state.phase == "finish":

    st.subheader("Sonuç")

    st.write(f"Doğru: {st.session_state.correct}")
    st.write(f"İpucu: {st.session_state.hints}")

    if st.button("Yeniden Başla"):
        st.session_state.clear()
        st.rerun()
