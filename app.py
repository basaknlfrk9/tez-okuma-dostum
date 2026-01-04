import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import json, uuid, time, re, traceback
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — ÖÖG DESTEKLİ & AKILLI REHBER SİSTEMİ
# =========================================================

DEBUG = True  # her şey düzeldikten sonra False yap

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# Tasarım
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 22px; }
    .stButton button {
        width: 100%; border-radius: 20px; height: 3.5em;
        font-weight: 600; font-size: 22px !important; transition: 0.3s;
        border: 3px solid #eee; background-color: #3498db; color: white;
    }
    .highlight-box {
        background-color: #ffffff; padding: 35px; border-radius: 30px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.08); border-left: 15px solid #f1c40f;
        font-size: 26px !important; line-height: 2.2 !important; margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# OpenAI Client
# ---------------------------
def get_ai_client():
    try:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        st.error("Secrets alanına OPENAI_API_KEY ekleyin.")
        st.stop()

client = get_ai_client()

# ---------------------------
# Google Sheets (stabil)
# ---------------------------
@st.cache_resource
def get_ws():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    info = dict(st.secrets["GSHEETS"])

    # Secrets bazen \\n olarak geliyor -> gerçek newline'a çevir
    pk = info.get("private_key", "")
    if isinstance(pk, str) and "\\n" in pk:
        info["private_key"] = pk.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(info, scopes=scope)
    gc = gspread.authorize(creds)

    sh = gc.open_by_url(st.secrets["GSHEET_URL"])

    if DEBUG:
        st.write("✅ Service account:", info.get("client_email"))
        st.write("✅ Sheet tabs:", [w.title for w in sh.worksheets()])

    ws = sh.worksheet("Performans")  # sekme adı birebir aynı olmalı
    return ws

def save_to_sheets(row):
    try:
        ws = get_ws()
        result = ws.append_row(row, value_input_option="USER_ENTERED")
        if DEBUG:
            st.success("✅ Satır eklendi (append_row OK)")
            st.write("append_row result:", result)
        return True
    except Exception:
        st.error("❌ Veri Kayıt Hatası (tam iz):")
        st.code(traceback.format_exc())
        return False

# ---------------------------
# Ses
# ---------------------------
def get_audio(text):
    clean = re.sub(r"[*#_]", "", text)
    clean = clean[:1000]
    tts = gTTS(text=clean, lang="tr")
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

# ---------------------------
# Session State Init
# ---------------------------
if "phase" not in st.session_state:
    st.session_state.phase = "auth"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Global çıkış
if st.session_state.phase != "auth":
    col_x, col_y = st.columns([9, 1])
    with col_y:
        if st.button("Çıkış 🚪"):
            st.session_state.clear()
            st.rerun()

# Debug: Sheets test (her fazda görünsün istersen)
if DEBUG:
    st.divider()
    st.subheader("🧪 Google Sheets Bağlantı Testi (DEBUG)")
    if st.button("TEST: Performans'a 1 satır yaz"):
        test_row = [
            "test_session", "test_user", "test_time", 0.1, "5",
            "%0", 6, 0, "Analiz", "Metin_1", 0, "Evet", "Evet", 0, 0
        ]
        ok = save_to_sheets(test_row)
        st.write("save_to_sheets sonucu:", ok)
    st.divider()

# =========================================================
# 1) GİRİŞ
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Adın Soyadın:")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])

    if st.button("Hadi Başlayalım! 🚀") and u:
        st.session_state.user = u
        st.session_state.sinif = s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) KURULUM
# =========================================================
elif st.session_state.phase == "setup":
    st.subheader("Okuyacağımız Metni Hazırlayalım")
    m_id = st.text_input("Metin ID:", "Metin_1")
    up = st.file_uploader("Metni PDF olarak yükle", type="pdf")
    txt = st.text_area("Veya metni buraya kopyala")

    if st.button("Metni Hazırla ✨") and (up or txt):
        raw = txt.strip()

        if up:
            reader = PdfReader(up)
            parts = []
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    parts.append(t)
            raw = "\n".join(parts).strip()

        if not raw:
            st.error("Metin boş görünüyor. PDF metin çıkarılamamış olabilir.")
            st.stop()

        with st.spinner("Metni senin için düzenliyorum..."):
            prompt = (
                "ÖÖG uzmanı olarak metni ortaokul öğrencisi için sadeleştir. "
                "6 soru içeren saf JSON üret. "
                "Şema: {'sade_metin': '...', 'sorular': "
                "[{'kok':'...','A':'...','B':'...','C':'...','dogru':'A','tur':'bilgi','ipucu':'...'}]}"
            )

            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": raw}
                ],
                response_format={"type": "json_object"}
            )

            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id

            st.session_state.phase = "read"
            st.session_state.q_idx = 0
            st.session_state.correct_map = {}
            st.session_state.hints = 0
            st.session_state.start_t = time.time()
            st.rerun()

# =========================================================
# 3) OKUMA VE SOHBET
# =========================================================
elif st.session_state.phase == "read":
    act = st.session_state.activity
    metin = act.get("sade_metin") or act.get("metin") or "Metin içeriği alınamadı."

    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Sesli Dinle"):
            st.audio(get_audio(metin), format="audio/mp3")

    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor")

    user_q = st.chat_input("Metinde anlamadığın bir yer var mı?")
    if user_q:
        ai_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Sen ÖÖG öğretmenisin. Şu metne göre yardım et: {metin}"},
                {"role": "user", "content": user_q}
            ]
        )
        st.session_state.chat_history.append({"q": user_q, "a": ai_resp.choices[0].message.content})

    for chat in st.session_state.chat_history:
        st.chat_message("user").write(chat["q"])
        st.chat_message("assistant").write(chat["a"])

    if st.button("Sorulara Geç ➔"):
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 4) SORULAR
# =========================================================
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get("sorular", [])
    i = st.session_state.q_idx

    # güvenlik: sorular gelmediyse
    if not sorular:
        st.error("Sorular bulunamadı. Üretilen JSON içinde 'sorular' alanı yok.")
        if DEBUG:
            st.write("activity:", act)
        st.stop()

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")
        st.markdown(f"<div style='font-size:24px; margin-bottom:20px;'>{q.get('kok','')}</div>", unsafe_allow_html=True)

        # Seçenekler
        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt,'')}", key=f"q_{i}_{opt}"):
                if opt == q.get("dogru"):
                    st.session_state.correct_map[i] = 1
                    st.success("🌟 Doğru!")
                    time.sleep(0.6)
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.session_state.correct_map[i] = 0
                    st.error("Tekrar dene!")

        if st.button("💡 İpucu Al", key=f"hint_{i}"):
            st.session_state.hints += 1
            st.warning(q.get("ipucu", "Metne bakabilirsin!"))

    else:
        # KAYIT BLOĞU
        if DEBUG:
            st.warning("✅ KAYIT BLOĞUNA GELDİM (debug)")
            st.write("q_idx:", st.session_state.q_idx, "len(sorular):", len(sorular))
            st.write("correct_map:", st.session_state.correct_map)

        dogru = sum(st.session_state.correct_map.values())
        sure = round((time.time() - st.session_state.start_t) / 60, 2)

        # A-O (15 sütun)
        row = [
            st.session_state.session_id,    # A: OturumID
            st.session_state.user,          # B: Kullanici
            st.session_state.login_time,    # C: TarihSaat
            sure,                           # D: SureDakika
            st.session_state.sinif,         # E: SinifDuzeyi
            f"%{round(dogru/6*100, 1)}",    # F: BasariYuzde
            6,                              # G: ToplamSoru
            dogru,                          # H: DogruSayi
            "Analiz",                       # I: HataliKazanim
            st.session_state.metin_id,      # J: MetinID
            st.session_state.hints,         # K: ToplamIpucu
            "Evet", "Evet", 0, 0            # L-O
        ]

        if DEBUG:
            st.write("📌 Yazılacak row:", row)

        if save_to_sheets(row):
            st.session_state.phase = "done"
            st.rerun()

# =========================================================
# 5) BİTTİ
# =========================================================
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Bugünkü çalışman kaydedildi!")

    if st.button("Yeni Metin"):
        st.session_state.phase = "setup"
        st.session_state.chat_history = []
        st.rerun()
