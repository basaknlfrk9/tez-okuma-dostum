import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError
import json, uuid, time, re, random, traceback
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — STRATEJİ TEMELLİ OKUMA (ÖÖG)
# PRE / DURING / POST + RATE LIMIT KORUMALI
# =========================================================
st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ------------------- TASARIM -------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 20px; }
.stButton button {
    width: 100%; border-radius: 18px; height: 3em;
    font-weight: 600; font-size: 20px !important;
    background-color: #3498db; color: white;
}
.highlight-box {
    background:#fff; padding:26px; border-radius:22px;
    border-left:12px solid #f1c40f;
    font-size:22px; line-height:1.9;
}
.card {
    background:#fff; padding:16px; border-radius:18px;
    border:1px solid #eee; margin-bottom:10px;
}
.small-note { color:#666; font-size:16px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# OPENAI CLIENT
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_json_request(system_prompt, user_text, max_retries=6):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                response_format={"type": "json_object"}
            )
        except (RateLimitError, APIError, APITimeoutError):
            wait = min(2 ** attempt, 20) + random.uniform(0, 1)
            st.warning(f"⚠️ Yoğunluk var, tekrar deneniyor... ({attempt+1}/{max_retries})")
            time.sleep(wait)

    st.error("❌ OpenAI yoğunluğu çok fazla. Lütfen 30 sn sonra tekrar deneyin.")
    st.stop()

# =========================================================
# GOOGLE SHEETS
# =========================================================
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    return get_gs_client().open_by_url(st.secrets["GSHEET_URL"])

def get_ws(name):
    sh = get_spreadsheet()
    for w in sh.worksheets():
        if w.title.lower() == name.lower():
            return w
    raise ValueError("Sekme bulunamadı:", name)

def log_to_sheet(row, sheet):
    try:
        get_ws(sheet).append_row(row, value_input_option="USER_ENTERED")
    except Exception:
        st.error("❌ Google Sheets Hatası")
        st.code(traceback.format_exc())

def log_chat(event, payload):
    ts = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")
    log_to_sheet(
        [st.session_state.session_id, st.session_state.user, ts, event, payload],
        "Sohbet"
    )

# =========================================================
# SESSION STATE
# =========================================================
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "busy" not in st.session_state: st.session_state.busy = False

# =========================================================
# GİRİŞ
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum")
    user = st.text_input("Öğrenci Kodun")
    sinif = st.selectbox("Sınıf", ["5", "6", "7", "8"])

    if st.button("Başla") and user:
        st.session_state.user = user
        st.session_state.sinif = sinif
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.phase = "setup"
        log_chat("LOGIN", f"sinif={sinif}")
        st.rerun()

# =========================================================
# METİN HAZIRLAMA
# =========================================================
elif st.session_state.phase == "setup":
    st.header("📄 Metin Yükle")
    metin_id = st.text_input("Metin ID", "Metin_1")
    pdf = st.file_uploader("PDF yükle", type="pdf")
    text = st.text_area("Veya metni yapıştır")

    if st.button("Metni Hazırla ✨"):
        if st.session_state.busy:
            st.warning("İşleniyor, lütfen bekle.")
            st.stop()

        st.session_state.busy = True

        raw = text
        if pdf:
            reader = PdfReader(pdf)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])

        raw = raw[:12000]  # RATE LIMIT KORUMA

        prompt = f"""
        ÖÖG uzmanı olarak {st.session_state.sinif}. sınıf için metni sadeleştir.
        6 soru üret.
        JSON:
        {{
          "sade_metin": "...",
          "sorular": [
            {{"kok":"...","A":"...","B":"...","C":"...","dogru":"A","tur":"literal/inferential/main_idea","ipucu":"..."}}
          ]
        }}
        """

        resp = openai_json_request(prompt, raw)
        st.session_state.activity = json.loads(resp.choices[0].message.content)
        st.session_state.metin_id = metin_id
        st.session_state.start_t = time.time()
        st.session_state.q_idx = 0
        st.session_state.correct = 0
        st.session_state.busy = False
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# SORULAR
# =========================================================
elif st.session_state.phase == "questions":
    qlist = st.session_state.activity["sorular"]
    i = st.session_state.q_idx

    if i < len(qlist):
        q = qlist[i]
        st.subheader(f"Soru {i+1}")
        st.write(q["kok"])
        for opt in ["A","B","C"]:
            if st.button(f"{opt}) {q[opt]}"):
                if opt == q["dogru"]:
                    st.session_state.correct += 1
                st.session_state.q_idx += 1
                st.rerun()
    else:
        sure = round((time.time()-st.session_state.start_t)/60, 2)
        log_to_sheet(
            [
                st.session_state.session_id,
                st.session_state.user,
                datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M"),
                sure,
                st.session_state.sinif,
                f"%{round(st.session_state.correct/6*100,1)}",
                6,
                st.session_state.correct,
                "Analiz",
                st.session_state.metin_id,
                0,"Evet","Evet",0,0
            ],
            "Performans"
        )
        st.success("✅ Çalışma kaydedildi")
        st.balloons()
