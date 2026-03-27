import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError
import json, uuid, time, re, random, traceback
from gtts import gTTS
from io import BytesIO
import pandas as pd

# =========================================================
# OKUMA DOSTUM — BANKA + SÜREÇ LOG
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Lexend', sans-serif;
    font-size: 20px;
    background: linear-gradient(180deg, #f8fbff 0%, #fffdf7 100%);
  }

  .main {
    background: linear-gradient(180deg, #f8fbff 0%, #fffdf7 100%);
  }

  h1, h2, h3 {
    color: #2c3e50;
    letter-spacing: 0.2px;
  }

  .stButton button {
    width: 100%;
    border-radius: 18px;
    height: 3.1em;
    font-weight: 700;
    font-size: 19px !important;
    border: none;
    background: linear-gradient(90deg, #4facfe 0%, #00c6ff 100%);
    color: white;
    box-shadow: 0 6px 14px rgba(79, 172, 254, 0.25);
    transition: all 0.18s ease-in-out;
  }

  .stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 18px rgba(79, 172, 254, 0.30);
    filter: brightness(1.03);
  }

  .stButton button:active {
    transform: scale(0.98);
  }

  .highlight-box {
    background: linear-gradient(180deg, #ffffff 0%, #fffef9 100%);
    padding: 28px;
    border-radius: 24px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.08);
    border-left: 12px solid #ffd54f;
    font-size: 22px !important;
    line-height: 1.9 !important;
    margin-bottom: 18px;
    white-space: pre-wrap;
  }

  .small-note {
    color: #5f6b7a;
    font-size: 16px;
    background: #f4f8ff;
    padding: 10px 14px;
    border-radius: 14px;
    border: 1px solid #dde9ff;
    margin-bottom: 8px;
  }

  .card {
    background: linear-gradient(180deg, #ffffff 0%, #fffdfa 100%);
    padding: 18px;
    border-radius: 22px;
    border: 1px solid #eef2f7;
    margin-bottom: 12px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.05);
  }

  .chat-user {
    background: linear-gradient(180deg, #eef7ff 0%, #e9f3ff 100%);
    padding: 14px;
    border-radius: 16px;
    margin-bottom: 8px;
    border: 1px solid #d7e9ff;
    box-shadow: 0 4px 10px rgba(0,0,0,0.03);
  }

  .chat-bot {
    background: linear-gradient(180deg, #fff8e8 0%, #fffdf6 100%);
    padding: 14px;
    border-radius: 16px;
    margin-bottom: 8px;
    border: 1px solid #ffe7ad;
    box-shadow: 0 4px 10px rgba(0,0,0,0.03);
  }

  .fun-badge {
    display: inline-block;
    background: linear-gradient(90deg, #ffe082 0%, #ffd54f 100%);
    color: #5d4037;
    padding: 8px 14px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 12px;
    box-shadow: 0 4px 10px rgba(255, 213, 79, 0.25);
  }

  .section-soft-blue {
    background: linear-gradient(180deg, #eef7ff 0%, #f8fbff 100%);
    border: 1px solid #dbeeff;
    border-radius: 22px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .section-soft-green {
    background: linear-gradient(180deg, #effcf5 0%, #f9fffb 100%);
    border: 1px solid #d8f5e3;
    border-radius: 22px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .section-soft-orange {
    background: linear-gradient(180deg, #fff6ea 0%, #fffdf9 100%);
    border: 1px solid #ffe5bf;
    border-radius: 22px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .mini-success {
    background: linear-gradient(90deg, #d4fc79 0%, #96e6a1 100%);
    color: #1f4d2e;
    padding: 10px 14px;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 600;
    margin: 8px 0 12px 0;
  }

  .mini-progress {
    background: #edf4ff;
    border-radius: 16px;
    overflow: hidden;
    height: 16px;
    margin: 8px 0 18px 0;
    border: 1px solid #dbe8ff;
  }

  .mini-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #43cea2 0%, #185a9d 100%);
    border-radius: 16px;
  }

  .badge-chip {
    display:inline-block;
    padding:8px 12px;
    border-radius:999px;
    background:linear-gradient(90deg,#ffd86f 0%, #fc6262 100%);
    color:white;
    font-weight:700;
    margin:4px 6px 4px 0;
    font-size:15px;
  }

  div[data-testid="stTextInput"] input,
  div[data-testid="stTextArea"] textarea {
    border-radius: 16px !important;
    border: 2px solid #e6eef8 !important;
    background: #ffffff !important;
    box-shadow: none !important;
  }

  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stTextArea"] textarea:focus {
    border: 2px solid #8ec5ff !important;
    box-shadow: 0 0 0 2px rgba(142, 197, 255, 0.18) !important;
  }

  div[data-testid="stRadio"] label,
  div[data-testid="stCheckbox"] label {
    font-size: 18px !important;
  }

  .stAlert {
    border-radius: 18px !important;
  }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def _norm(x) -> str:
    return str(x or "").strip()

def now_tr() -> str:
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

def extract_metin_number(metin_id: str) -> int:
    s = _norm(metin_id)
    m = re.search(r"(\d+)", s)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0

def expected_question_count(metin_id: str) -> int:
    n = extract_metin_number(metin_id)
    return 7 if n >= 8 else 6

def option_letters_for_metin(metin_id: str):
    n = extract_metin_number(metin_id)
    return ["A", "B", "C"] if (n and n < 5) else ["A", "B", "C", "D"]

def get_audio(text: str):
    clean = re.sub(r"[*#_]", "", (text or ""))[:1000]
    try:
        tts = gTTS(text=clean, lang="tr")
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception:
        st.error("❌ Ses oluşturulamadı. Lütfen tekrar deneyin.")
        return None

# =========================================================
# MOTIVATION + TEMPLATE + BADGES
# =========================================================
def get_motivation_message(phase: str, progress: float = 0.0) -> str:
    if phase == "pre":
        msgs = [
            "🌟 Harika, başlamaya hazırsın!",
            "🧠 Önce biraz düşünelim, sonra okumaya geçeceğiz.",
            "👏 Güzel gidiyorsun, şimdi metne hazırlanıyoruz."
        ]
    elif phase == "during":
        if progress < 0.34:
            msgs = [
                "📖 Harika başladın, böyle devam et!",
                "👀 Dikkatini çok güzel topluyorsun.",
                "🌈 İlk bölümleri başarıyla okuyorsun."
            ]
        elif progress < 0.67:
            msgs = [
                "💪 Çok iyi gidiyorsun, yarısına geldin!",
                "🔍 İstersen tekrar okuyabilir ya da dinleyebilirsin.",
                "⭐ Şimdiye kadar çok güzel ilerledin."
            ]
        else:
            msgs = [
                "🚀 Az kaldı, son bölümlere geldin!",
                "🌟 Biraz daha dikkat, bitirmek üzeresin.",
                "👏 Harika sabrettin, neredeyse tamam!"
            ]
    elif phase == "post":
        msgs = [
            "🧠 Şimdi düşündüklerini toplama zamanı.",
            "✍️ Kendi cümlelerinle anlatman çok değerli.",
            "🌟 Şimdi metni hatırlayıp anlatabilirsin."
        ]
    elif phase == "questions":
        msgs = [
            "⭐ Sorulara geçtin, harika!",
            "💪 Elinden geleni yap, istersen ipucu alabilirsin.",
            "🎯 Soruları çözerken metne geri bakabilirsin."
        ]
    else:
        msgs = ["🌟 Güzel gidiyorsun!"]
    return random.choice(msgs)

def get_storymap_templates():
    return {
        "kahraman": "Bu öyküde ... vardı.",
        "mekan": "Olay ... yerinde geçti.",
        "zaman": "Olay ... zamanında oldu.",
        "problem": "Sorun şuydu: ...",
        "olaylar": "Önce ... oldu. Sonra ... oldu. En son ... oldu.",
        "cozum": "Sonunda ... oldu."
    }

def award_badge(name: str):
    badges = st.session_state.get("badges", [])
    if name not in badges:
        badges.append(name)
    st.session_state.badges = badges

def render_badges():
    badges = st.session_state.get("badges", [])
    if badges:
        html = "".join([f"<span class='badge-chip'>{b}</span>" for b in badges])
        st.markdown(f"<div>{html}</div>", unsafe_allow_html=True)

# =========================================================
# METİN BÖLME
# =========================================================
def _split_sentences_tr(s: str):
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", s)
    return [p.strip() for p in parts if p.strip()]

def _force_split_long_text(text: str, max_len: int):
    text = (text or "").strip()
    if len(text) <= max_len:
        return [text]

    if "," in text:
        pieces, buf = [], ""
        for part in text.split(","):
            part = part.strip()
            candidate = (buf + (", " if buf else "") + part).strip()
            if len(candidate) <= max_len:
                buf = candidate
            else:
                if buf:
                    pieces.append(buf)
                buf = part
        if buf:
            pieces.append(buf)
        return pieces

    for conj in [" çünkü ", " ama ", " fakat ", " ancak ", " ve ", " sonra ", " böylece "]:
        if conj in text:
            chunks, buf = [], ""
            parts = text.split(conj)
            for i, part in enumerate(parts):
                part = part.strip()
                glue = conj.strip() if i > 0 else ""
                candidate = (buf + (" " + glue + " " if buf and glue else "") + part).strip()
                if len(candidate) <= max_len:
                    buf = candidate
                else:
                    if buf:
                        chunks.append(buf)
                    buf = (glue + " " + part).strip() if glue else part
            if buf:
                chunks.append(buf)

            final = []
            for c in chunks:
                if len(c) > max_len:
                    final.extend(_force_split_long_text(c, max_len=max_len))
                else:
                    final.append(c)
            return final

    words = text.split()
    out, buf = [], ""
    for w in words:
        cand = (buf + " " + w).strip()
        if len(cand) <= max_len:
            buf = cand
        else:
            if buf:
                out.append(buf)
            buf = w
    if buf:
        out.append(buf)
    return out

def split_paragraphs(text: str, target_min=500, target_max=800, tail_min=180):
    text = (text or "").replace("\r", "\n").strip()
    if not text:
        return []

    text = re.sub(r"\n{3,}", "\n\n", text)
    placeholder = "<<<P>>>"
    text = re.sub(r"\n\s*\n", placeholder, text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(placeholder, "\n\n")

    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not raw_paras:
        raw_paras = [text]

    merged = []
    buf = ""
    for p in raw_paras:
        if not buf:
            buf = p
        else:
            if len(buf) < target_min:
                buf = (buf + " " + p).strip()
            else:
                merged.append(buf)
                buf = p
    if buf:
        merged.append(buf)

    out = []
    for para in merged:
        sents = _split_sentences_tr(para)
        if not sents:
            out.extend(_force_split_long_text(para, max_len=target_max))
            continue

        block = ""
        for s in sents:
            if not block:
                block = s
                if len(block) > target_max:
                    out.extend(_force_split_long_text(block, max_len=target_max))
                    block = ""
                continue

            cand = (block + " " + s).strip()
            if len(cand) <= target_max:
                block = cand
            else:
                if len(block) < target_min:
                    pieces = _force_split_long_text(
                        s,
                        max_len=max(200, target_max - len(block) - 1)
                    )
                    for piece in pieces:
                        cand2 = (block + " " + piece).strip()
                        if len(cand2) <= target_max:
                            block = cand2
                        else:
                            out.append(block)
                            block = piece
                else:
                    out.append(block)
                    block = s

                if len(block) > target_max:
                    out.extend(_force_split_long_text(block, max_len=target_max))
                    block = ""

        if block:
            out.append(block)

    final = []
    buf = ""
    for b in out:
        if not buf:
            buf = b
        else:
            if len(buf) < target_min and (len(buf) + 1 + len(b)) <= (target_max + 300):
                buf = (buf + " " + b).strip()
            else:
                final.append(buf)
                buf = b
    if buf:
        final.append(buf)

    if len(final) >= 2 and len(final[-1]) < tail_min:
        if len(final[-2]) + 1 + len(final[-1]) <= (target_max + 350):
            final[-2] = (final[-2] + " " + final[-1]).strip()
            final.pop()

    return final

# =========================================================
# OPENAI
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_json_request(system_prompt, user_text, model="gpt-4o-mini", max_retries=6, temperature=0):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
        except (RateLimitError, APIError, APITimeoutError):
            wait = min(2 ** attempt, 20) + random.uniform(0, 1.0)
            st.warning(f"⚠️ Yoğunluk var, tekrar deneniyor... ({attempt+1}/{max_retries})")
            time.sleep(wait)
    st.error("❌ OpenAI yoğunluğu çok fazla. Biraz sonra tekrar deneyin.")
    st.stop()

def openai_text_request(system_prompt, user_text, model="gpt-4o-mini", max_retries=6, temperature=0.3):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                temperature=temperature,
            )
        except (RateLimitError, APIError, APITimeoutError):
            wait = min(2 ** attempt, 20) + random.uniform(0, 1.0)
            st.warning(f"⚠️ Yoğunluk var, tekrar deneniyor... ({attempt+1}/{max_retries})")
            time.sleep(wait)
    st.error("❌ OpenAI yoğunluğu çok fazla. Biraz sonra tekrar deneyin.")
    st.stop()

def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""
    try:
        bio = BytesIO(audio_bytes)
        bio.name = "speech.wav"
        resp = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=bio
        )
        text = getattr(resp, "text", "") or ""
        return text.strip()
    except Exception:
        try:
            bio = BytesIO(audio_bytes)
            bio.name = "speech.wav"
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=bio
            )
            text = getattr(resp, "text", "") or ""
            return text.strip()
        except Exception:
            return ""

# =========================================================
# CHATBOT FONKSİYONLARI
# =========================================================
def generate_ai_hint(metin: str, soru: dict, wrong_choice: str, level: int = 1):
    opts_payload = {}
    for k in ["A", "B", "C", "D"]:
        if soru.get(k):
            opts_payload[k] = soru.get(k)

    if level == 1:
        level_instruction = """
- Çok genel bir ipucu ver.
- Cevabı söyleme.
- Öğrenciyi sadece doğru bölüme yönlendir.
"""
    elif level == 2:
        level_instruction = """
- Biraz daha açık ipucu ver.
- Hâlâ doğru cevabı söyleme.
- Sorunun neye dikkat ettiğini sezdir.
"""
    else:
        level_instruction = """
- En açık ipucunu ver ama doğru seçeneği doğrudan söyleme.
- Öğrenciyi doğru cevaba çok yaklaştır.
"""

    sys = f"""
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine destek olan sabırlı bir okuma koçusun.
Görevin cevabı doğrudan söylemeden kısa, anlaşılır ve yönlendirici bir ipucu vermek.

Kurallar:
- Türkçe yaz.
- En fazla 2 cümle yaz.
- Doğru seçeneği ASLA söyleme.
- Öğrenciyi metindeki ilgili bölüme yönlendir.
- Yaş düzeyine uygun ve motive edici ol.
{level_instruction}
"""
    payload = {
        "metin": (metin or "")[:2500],
        "soru": soru.get("kok", ""),
        "seçenekler": opts_payload,
        "ogrencinin_secimi": wrong_choice,
        "dogru_cevap": soru.get("dogru", ""),
        "ipucu_seviyesi": level
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.2)
    return resp.choices[0].message.content.strip()

def generate_summary_feedback(metin: str, ozet: str):
    sys = """
Sen destekleyici bir okuma öğretmenisin.
Öğrencinin özetine kısa geri bildirim ver.
Kurallar:
- Türkçe yaz.
- En fazla 3 cümle olsun.
- Önce güçlü yönünü söyle.
- Sonra tek bir geliştirme önerisi ver.
- Nazik ve açık ol.
"""
    payload = {
        "metin": (metin or "")[:2500],
        "ogrenci_ozeti": (ozet or "")[:1000]
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.3)
    return resp.choices[0].message.content.strip()

def generate_storymap_feedback(metin: str, sm: dict):
    sys = """
Sen öğrencinin öykü haritasını değerlendiren destekleyici bir öğretmensin.

Kurallar:
- Türkçe yaz.
- En fazla 3 cümle olsun.
- İlk cümlede öğrencinin iyi yaptığı bir şeyi söyle.
- İkinci cümlede sadece 1 geliştirme önerisi ver.
- Cevabı doğrudan verme.
- Nazik, motive edici ve kısa ol.
"""
    payload = {
        "metin": (metin or "")[:2500],
        "story_map": sm
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.3)
    return resp.choices[0].message.content.strip()

def chat_about_text(metin: str, user_message: str, chat_history=None):
    history = chat_history or []

    messages = [
        {
            "role": "system",
            "content": """
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine metin okuma desteği veren bir eğitim chatbotusun.
Kurallar:
- Türkçe yaz.
- Kısa, açık ve motive edici ol.
- Cevabı hemen vermek yerine öğrenciyi düşündür.
- Öğrenciyi metindeki ipuçlarına yönlendir.
- Metin dışına taşma.
"""
        }
    ]

    for item in history[-6:]:
        messages.append({"role": item["role"], "content": item["content"]})

    messages.append({
        "role": "user",
        "content": f"METİN:\n{(metin or '')[:3000]}\n\nÖĞRENCİ MESAJI:\n{user_message}"
    })

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()

def explain_word_simple(word: str, metin: str):
    sys = """
Sen çocuklara kelimeyi çok basit anlatan bir öğretmensin.
Kurallar:
- Türkçe yaz.
- En fazla 2 kısa cümle olsun.
- Kelimenin anlamını çok basit açıkla.
- Gerekirse metindeki kullanıma göre açıkla.
"""
    payload = {
        "kelime": word,
        "metin": (metin or "")[:1200]
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.2)
    return resp.choices[0].message.content.strip()

# =========================================================
# GOOGLE SHEETS
# =========================================================
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    pk = info.get("private_key", "")
    if isinstance(pk, str) and "\\n" in pk:
        info["private_key"] = pk.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    return get_gs_client().open_by_url(st.secrets["GSHEET_URL"])

def get_ws(sheet_name: str):
    sh = get_spreadsheet()
    wanted = sheet_name.strip().lower()
    for w in sh.worksheets():
        if w.title.strip().lower() == wanted:
            return w
    raise ValueError(f"Sheet sekmesi bulunamadı: '{sheet_name}'. Mevcut: {[w.title for w in sh.worksheets()]}")

@st.cache_data(ttl=300)
def read_sheet_records(sheet_name: str):
    ws = get_ws(sheet_name)
    return ws.get_all_records()

def append_row_safe(sheet_name: str, row):
    try:
        ws = get_ws(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        st.error(f"❌ Sheets yazma hatası ({sheet_name})")
        st.code(traceback.format_exc())
        return False

# =========================================================
# OKUMA SÜRECİ LOG
# =========================================================
def save_reading_process(kayit_turu: str, icerik: str, paragraf_no=None):
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        "",
        st.session_state.get("metin_id", ""),
        paragraf_no if paragraf_no is not None else "",
        kayit_turu,
        (icerik or "")[:45000],
    ]
    append_row_safe("OkumaSüreci", row)

# =========================================================
# ÜSTBİLİŞSEL RUBRİK
# =========================================================
def compute_metacog_signals():
    qa = st.session_state.get("question_attempts", {}) or {}
    try:
        attempts_total = sum(int(v) for v in qa.values())
    except Exception:
        attempts_total = 0

    return {
        "prediction_len": len((st.session_state.get("prediction") or "").strip()),
        "attention_ok": bool(st.session_state.get("attention_ok", False)),
        "speed": st.session_state.get("reading_speed", ""),
        "repeat_count": int(st.session_state.get("repeat_count", 0)),
        "tts_count": int(st.session_state.get("tts_count", 0)),
        "reread_count": int(st.session_state.get("reread_count", 0)),
        "hints": int(st.session_state.get("hints", 0)),
        "attempts_total": int(attempts_total),
        "summary_len": len((st.session_state.get("summary") or "").strip()),
        "important_note_len": len((st.session_state.get("final_important_note") or "").strip()),
        "prior_knowledge_len": len((st.session_state.get("prior_knowledge") or "").strip()),
        "story_map_total": int(st.session_state.get("story_map_last_total") or 0),
        "story_map_filled": int(st.session_state.get("story_map_filled") or 0),
        "reflection_strategy_len": len((st.session_state.get("reflection_strategy") or "").strip()),
        "reflection_next_len": len((st.session_state.get("reflection_next_time") or "").strip()),
    }

def rule_based_metacog_score(sig):
    plan = 0
    if sig["prediction_len"] >= 5:
        plan += 1
    if sig["attention_ok"]:
        plan += 1
    plan = min(plan, 2)

    monitor = 0
    if (sig["reread_count"] + sig["tts_count"]) >= 1:
        monitor += 1
    if sig["hints"] >= 1:
        monitor += 1
    if sig["attempts_total"] >= 2:
        monitor += 1
    monitor = min(monitor, 3)

    evals = 0
    if sig["summary_len"] >= 20:
        evals += 1
    if sig["important_note_len"] >= 10:
        evals += 1
    if sig["story_map_total"] >= 6 or sig["story_map_filled"] >= 4:
        evals += 1
    evals = min(evals, 3)

    transfer = 0
    if sig["reflection_next_len"] >= 8:
        transfer = 1
    if sig["reflection_next_len"] >= 20:
        transfer = 2

    total = plan + monitor + evals + transfer
    reason = "Kural tabanlı rubrik (planlama/izleme/değerlendirme/transfer)."
    return {"planlama": plan, "izleme": monitor, "degerlendirme": evals, "transfer": transfer, "total": total, "reason": reason}

def save_metacog_rubric_row(scores: dict, reason: str, signals: dict):
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        st.session_state.get("metin_id", ""),
        int(scores.get("planlama", 0)),
        int(scores.get("izleme", 0)),
        int(scores.get("degerlendirme", 0)),
        int(scores.get("transfer", 0)),
        int(scores.get("total", 0)),
        (reason or "")[:500],
        json.dumps(signals, ensure_ascii=False)[:45000],
    ]
    return append_row_safe("UstBilisselRubrik", row)

# =========================================================
# BANKA OKUMA
# =========================================================
def list_metin_ids():
    rows = read_sheet_records("MetinBankasi")
    ids = []
    for r in rows:
        if _norm(r.get("metin_id")):
            ids.append(_norm(r.get("metin_id")))
    return sorted(list(set(ids)))

def load_activity_from_bank(metin_id: str):
    mrows = read_sheet_records("MetinBankasi")

    def normrow(r: dict):
        return {str(k).strip().lower(): ("" if r.get(k) is None else str(r.get(k)).strip()) for k in r.keys()}

    mrows_n = [normrow(r) for r in mrows]
    match_m = [r for r in mrows_n if _norm(r.get("metin_id")) == _norm(metin_id)]
    if not match_m:
        return None, "MetinBankasi'nda bu metin_id bulunamadı."

    metin = _norm(match_m[0].get("metin"))
    baslik = _norm(match_m[0].get("baslik"))
    pre_ipucu = _norm(match_m[0].get("pre_ipucu"))

    if not metin:
        return None, "MetinBankasi'nda metin alanı boş."

    qrows = read_sheet_records("SoruBankasi")
    qrows_n = [normrow(r) for r in qrows]
    match_q = [r for r in qrows_n if _norm(r.get("metin_id")) == _norm(metin_id)]
    if not match_q:
        return None, "SoruBankasi'nda bu metin_id için soru bulunamadı."

    def qno(r):
        s = str(r.get("soru_no", "")).strip()
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else 0

    match_q = sorted(match_q, key=qno)
    opts = option_letters_for_metin(metin_id)

    def get_opt(r, L):
        candidates = [L.lower(), L.lower().strip(), L.strip().lower()]
        for c in candidates:
            v = r.get(c)
            if v is not None and str(v).strip():
                return _norm(v)
        return ""

    sorular = []
    for r in match_q:
        kok = _norm(r.get("kok")) or "(Soru kökü eksik)"
        dogru = _norm(r.get("dogru")).upper() or opts[0]
        if dogru not in opts:
            dogru = opts[0]
        q_obj = {"kok": kok, "dogru": dogru}
        for L in opts:
            q_obj[L] = get_opt(r, L)
        sorular.append(q_obj)

    exp_n = expected_question_count(metin_id)
    if len(sorular) != exp_n:
        diag = f"Bulunan soru={len(sorular)} / Beklenen={exp_n}. "
        diag += "Kontrol: SoruBankasi başlıkları (metin_id, soru_no, kok, A, B, C, (D varsa), dogru) doğru mu?"
        return None, diag

    return {"sade_metin": metin, "baslik": baslik, "pre_ipucu": pre_ipucu, "sorular": sorular, "opts": opts}, ""

# =========================================================
# STORY MAP AI
# =========================================================
def _tr_lower_story(s: str) -> str:
    s = str(s or "")
    repl = str.maketrans({
        "I": "ı", "İ": "i",
        "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"
    })
    return s.translate(repl).lower()

def _normalize_story_text(s: str) -> str:
    s = _tr_lower_story(s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _story_replace_synonyms(s: str) -> str:
    s = " " + _normalize_story_text(s) + " "

    synonym_map = {
        "yuva": ["ev", "evi", "barinak", "barınağı", "barinagi"],
        "yikildi": ["bozuldu", "zarar gordu", "zarar gördü", "dagildi", "dağıldı", "coktu", "çöktü"],
        "kus": ["kuş", "yavru kus", "yavru kuş", "kucuk kus", "küçük kuş"],
        "uzuldu": ["uzgun", "üzgün", "cok uzuldu", "çok üzüldü"],
        "yardim": ["destek", "yardim etti", "yardım etti", "yardimci oldu", "yardımcı oldu"],
        "orman": ["agaclik", "ağaçlık", "agac", "ağaç"],
        "sabah": ["gunduz", "gündüz", "erken", "sabah vakti"],
        "cozum": ["sonuc", "sonuç", "care", "çare"]
    }

    for canon, variants in synonym_map.items():
        for v in variants:
            s = s.replace(f" {v} ", f" {canon} ")

    return re.sub(r"\s+", " ", s).strip()

def _find_best_evidence_span(metin: str, answer: str, max_words: int = 16) -> str:
    metin = str(metin or "")
    answer = str(answer or "").strip()
    if not metin or not answer:
        return ""

    ans_norm = _story_replace_synonyms(answer)
    ans_tokens = set(ans_norm.split())
    if not ans_tokens:
        return ""

    sentences = re.split(r"(?<=[.!?…])\s+|\n+", metin)

    best_sent = ""
    best_score = 0.0

    for sent in sentences:
        sent_norm = _story_replace_synonyms(sent)
        sent_tokens = set(sent_norm.split())
        if not sent_tokens:
            continue

        overlap = ans_tokens & sent_tokens
        coverage = len(overlap) / max(len(ans_tokens), 1)
        substring_bonus = 0.35 if ans_norm in sent_norm else 0
        score = coverage + substring_bonus

        if score > best_score:
            best_score = score
            best_sent = sent.strip()

    if best_score <= 0:
        return ""

    words = best_sent.split()
    if len(words) <= max_words:
        return best_sent
    return " ".join(words[:max_words])

def _score_single_story_field_rule(answer: str, metin: str, field_name: str = ""):
    answer = str(answer or "").strip()
    if not answer:
        return 0, "", "Boş cevap"

    raw_answer_norm = _normalize_story_text(answer)
    smart_answer_norm = _story_replace_synonyms(answer)

    ans_tokens = set(smart_answer_norm.split())
    if not ans_tokens:
        return 0, "", "Anlamlı kelime yok"

    raw_metin_norm = _normalize_story_text(metin)
    smart_metin_norm = _story_replace_synonyms(metin)

    evidence = _find_best_evidence_span(metin, answer)

    if raw_answer_norm and raw_answer_norm in raw_metin_norm:
        return 2, evidence or answer, "Metinde doğrudan geçti"

    if smart_answer_norm and smart_answer_norm in smart_metin_norm:
        return 2, evidence or answer, "Eşdeğer anlamla metinde geçti"

    metin_tokens = set(smart_metin_norm.split())
    overlap = ans_tokens & metin_tokens
    coverage = len(overlap) / max(len(ans_tokens), 1)

    if len(ans_tokens) == 1 and len(overlap) == 1:
        return 2, evidence or answer, "Tek kelimelik güçlü eşleşme"

    if field_name in {"problem", "olaylar", "cozum"}:
        if coverage >= 0.60:
            return 2, evidence or answer, "Anlamsal güçlü eşleşme"
        elif coverage >= 0.30:
            return 1, evidence or answer, "Anlamsal kısmi eşleşme"
        else:
            return 0, "", "Eşleşme zayıf"

    if coverage >= 0.80:
        return 2, evidence or answer, "Güçlü kelime eşleşmesi"
    elif coverage >= 0.40:
        return 1, evidence or answer, "Kısmi kelime eşleşmesi"
    else:
        return 0, "", "Kelime eşleşmesi zayıf"

def _llm_semantic_score(field_name: str, answer: str, metin: str):
    answer = str(answer or "").strip()
    if not answer:
        return 0, "", "Boş cevap"

    metin_short = (metin or "")[:5000]

    sys = f"""
Sen ilkokul/ortaokul düzeyinde öykü haritası puanlayan çok dikkatli bir öğretmensin.

Alan: {field_name}

0 puan:
- Cevap metinle uyuşmuyor
- Metinde destek yok
- Yanlış, alakasız veya uydurma

1 puan:
- Cevap kısmen doğru
- Eksik, çok genel veya belirsiz

2 puan:
- Cevap metindeki bilgiyle açıkça uyumlu
- Eş anlamlı / sadeleştirilmiş cevaplar kabul edilir

Kurallar:
- Sadece JSON üret.
- evidence alanına metinden kısa bir kanıt yaz.
- reason kısa olsun.
- score sadece 0, 1 veya 2 olsun.

JSON şeması:
{{
  "score": 0,
  "evidence": "",
  "reason": ""
}}
"""
    user = json.dumps({
        "alan": field_name,
        "ogrenci_cevabi": answer,
        "metin": metin_short
    }, ensure_ascii=False)

    try:
        resp = openai_json_request(sys, user, model="gpt-4o-mini", temperature=0)
        raw = resp.choices[0].message.content
        data = json.loads(raw)

        score = int(data.get("score", 0))
        score = max(0, min(2, score))
        evidence = str(data.get("evidence", "") or "").strip()[:180]
        reason = str(data.get("reason", "") or "").strip()[:160]
        return score, evidence, reason
    except Exception:
        return 0, "", "LLM puanı alınamadı"

def ai_score_story_map(metin: str, sm: dict):
    alanlar = ["kahraman", "mekan", "zaman", "problem", "olaylar", "cozum"]
    kural_agirlikli = {"kahraman", "mekan", "zaman"}

    out = {}
    reasons = {}

    for key in alanlar:
        answer = sm.get(key, "")
        rule_score, rule_ev, rule_reason = _score_single_story_field_rule(answer, metin, key)

        if key in kural_agirlikli:
            out[key] = int(rule_score)
            reasons[key] = rule_reason
            continue

        if not str(answer or "").strip():
            out[key] = 0
            reasons[key] = "Boş cevap"
            continue

        llm_score, llm_ev, llm_reason = _llm_semantic_score(key, answer, metin)
        final_score = max(rule_score, llm_score)

        out[key] = int(final_score)
        reasons[key] = llm_reason or rule_reason or "Değerlendirildi"

    total = sum(out.values())

    iyi = [k for k, v in out.items() if v == 2]
    orta = [k for k, v in out.items() if v == 1]
    zayif = [k for k, v in out.items() if v == 0 and str(sm.get(k, "")).strip()]

    parts = []
    if iyi:
        parts.append("Güçlü: " + ", ".join(iyi))
    if orta:
        parts.append("Kısmi: " + ", ".join(orta))
    if zayif:
        parts.append("Zayıf: " + ", ".join(zayif))

    reason = " | ".join(parts) if parts else "Tamamlandı"
    reason = reason[:220]
    return out, total, reason

def save_story_map_row(sm: dict, scores: dict, total: int, reason: str):
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        "",
        st.session_state.get("metin_id", ""),
        sm.get("kahraman", ""),
        sm.get("mekan", ""),
        sm.get("zaman", ""),
        sm.get("problem", ""),
        sm.get("olaylar", ""),
        sm.get("cozum", ""),
        sum(1 for _, v in sm.items() if str(v).strip()),
        scores.get("kahraman", 0),
        scores.get("mekan", 0),
        scores.get("zaman", 0),
        scores.get("problem", 0),
        scores.get("olaylar", 0),
        scores.get("cozum", 0),
        total,
        reason,
    ]
    return append_row_safe("OykuHaritasi", row)

# =========================================================
# WORD HELPERS
# =========================================================
def extract_candidate_words(text: str, min_len: int = 6, max_count: int = 20):
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text or "")
    cleaned = []
    stop = {
        "çünkü","ancak","sonunda","olarak","içinde","olduğu","olarak","sonra","önce",
        "birlikte","küçük","büyük","onların","olunca","metinde","sorular","kahraman",
        "mekan","zaman","problem","olaylar","çözüm","cozum"
    }
    for t in tokens:
        tl = t.lower()
        if len(tl) >= min_len and tl not in stop:
            cleaned.append(t)
    uniq = []
    for w in cleaned:
        if w.lower() not in [u.lower() for u in uniq]:
            uniq.append(w)
    return uniq[:max_count]

# =========================================================
# SESSION STATE INIT
# =========================================================
def reset_activity_states():
    st.session_state.chat_history = []
    st.session_state.saved_perf = False
    st.session_state.busy = False

    st.session_state.prediction = ""
    st.session_state.attention_ok = False
    st.session_state.reading_speed = "Orta"

    st.session_state.repeat_count = 0
    st.session_state.tts_count = 0
    st.session_state.reread_count = 0

    st.session_state.final_important_note = ""
    st.session_state.final_important_saved = False

    st.session_state.prior_knowledge = ""
    st.session_state.summary = ""

    st.session_state.story_map = {"kahraman": "", "mekan": "", "zaman": "", "problem": "", "olaylar": "", "cozum": ""}
    st.session_state.story_map_ai_scored = False
    st.session_state.story_map_last_total = None
    st.session_state.story_map_last_reason = ""
    st.session_state.story_map_filled = 0

    st.session_state.skipped = []
    st.session_state.hints_used_by_q = {}
    st.session_state.hint_level_by_q = {}
    st.session_state.correct_no_hint = 0
    st.session_state.correct_with_hint = 0
    st.session_state.question_attempts = {}
    st.session_state.show_text_in_questions = False

    st.session_state.reflection_strategy = ""
    st.session_state.reflection_next_time = ""

    st.session_state.last_report = {}

    st.session_state.ai_hint_text = ""
    st.session_state.summary_feedback = ""
    st.session_state.storymap_feedback = ""
    st.session_state.chat_messages = []
    st.session_state.badges = []
    st.session_state.last_word_help = ""
    st.session_state.word_help_answer = ""
    st.session_state.voice_text = ""

if "phase" not in st.session_state:
    st.session_state.phase = "auth"
if "busy" not in st.session_state:
    st.session_state.busy = False

if st.session_state.phase != "auth":
    col_a, col_b = st.columns([9, 1])
    with col_b:
        if st.button("Çıkış 🚪"):
            st.session_state.clear()
            st.rerun()

# =========================================================
# 1) AUTH
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    st.markdown("<div class='fun-badge'>🎉 Bugün birlikte okuyup keşfedeceğiz!</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-soft-blue'><b>Hazır mısın?</b><br/>Önce öğrenci kodunu gir, sonra metnini seç ve başlayalım.</div>", unsafe_allow_html=True)

    u = st.text_input("Öğrenci Kodun (örn: S5-014):")

    try:
        metin_ids_all = list_metin_ids()
    except Exception:
        metin_ids_all = []
        st.error("❌ MetinBankasi okunamadı. Sekme adlarını ve erişimi kontrol et.")
        st.code(traceback.format_exc())

    selected_id = st.selectbox("Metin seç:", metin_ids_all) if metin_ids_all else st.text_input("Metin ID:", "Metin_001")
    st.caption("Sınıf seçimi kaldırıldı. Metin seçince devam edilir.")

    if st.button("Hadi Başlayalım! 🚀") and u and selected_id:
        st.session_state.user = u
        st.session_state.metin_id = selected_id
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
        reset_activity_states()
        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) SETUP
# =========================================================
elif st.session_state.phase == "setup":
    st.subheader("📄 Metin Hazırla (Sistemden)")
    st.markdown("<div class='fun-badge'>✨ Metnimizi hazırlıyoruz</div>", unsafe_allow_html=True)

    selected_id = st.session_state.get("metin_id", "")
    if not selected_id:
        st.error("Metin seçilmemiş. Baştan giriş yap.")
        st.stop()

    st.markdown(f"<div class='card'><b>Seçili Metin</b><br/>{selected_id}</div>", unsafe_allow_html=True)
    st.caption("Metin ve sorular Google Sheets bankasından çekilir.")

    if st.button("Metni Hazırla ✨", disabled=st.session_state.busy):
        st.session_state.busy = True

        activity, err = load_activity_from_bank(selected_id)
        if activity is None:
            st.session_state.busy = False
            st.error(f"❌ Yüklenemedi: {err}")
            st.stop()

        st.session_state.activity = activity
        st.session_state.paragraphs = split_paragraphs(
            activity.get("sade_metin", ""),
            target_min=500,
            target_max=800,
            tail_min=180
        )
        st.session_state.p_idx = 0
        st.session_state.q_idx = 0
        st.session_state.correct_map = {}
        st.session_state.hints = 0
        st.session_state.start_t = time.time()
        st.session_state.saved_perf = False

        save_reading_process("SESSION_START", f"Metin yüklendi: {selected_id}", paragraf_no=None)

        st.session_state.busy = False
        st.session_state.phase = "pre"
        st.rerun()

# =========================================================
# 3) PRE
# =========================================================
elif st.session_state.phase == "pre":
    st.subheader("🟦 Okuma Öncesi (PRE-READING)")
    st.markdown("<div class='fun-badge'>🧩 1. Aşama: Hazırlanıyoruz</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='mini-progress'>
        <div class='mini-progress-fill' style='width: 25%;'></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='section-soft-blue'><b>Hazırlık Zamanı</b><br/>Önce metin hakkında biraz düşünelim.</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='mini-success'>{get_motivation_message('pre')}</div>", unsafe_allow_html=True)

    baslik = st.session_state.activity.get("baslik", "")
    pre_ipucu = st.session_state.activity.get("pre_ipucu", "")

    if baslik:
        st.markdown(f"<div class='card'><b>Metnin Başlığı</b><br/>{baslik}</div>", unsafe_allow_html=True)
    if pre_ipucu:
        st.markdown(f"<div class='card'><b>Küçük İpucu</b><br/>{pre_ipucu}</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'><b>1) Merak Uyandırma</b><br/>Bu metinde ilginç bir durum var. Sence ne olabilir?</div>", unsafe_allow_html=True)
    curiosity = st.text_input("Tahminin (1 cümle):", value=st.session_state.prediction)

    st.markdown("<div class='card'><b>2) Dikkat Toplama</b><br/>Şimdi metni dikkatle okuyacağız. Hazır mısın?</div>", unsafe_allow_html=True)
    attention = st.checkbox("✅ Hazırım (dikkatimi veriyorum)", value=st.session_state.attention_ok)

    st.markdown("<div class='card'><b>3) Okuma Hızı Seç</b><br/>Bugün nasıl okumak istersin?</div>", unsafe_allow_html=True)
    speed = st.radio("Okuma hızı:", ["Yavaş", "Orta", "Hızlı"], index=["Yavaş", "Orta", "Hızlı"].index(st.session_state.reading_speed))

    if st.button("Okumaya Başla ➜"):
        st.session_state.prediction = curiosity.strip()
        st.session_state.attention_ok = attention
        st.session_state.reading_speed = speed

        if st.session_state.prediction:
            save_reading_process("PRE_PREDICTION", st.session_state.prediction, paragraf_no=None)
            award_badge("🔮 Tahmin Yaptım")
        save_reading_process("PRE_ATTENTION", "Evet" if attention else "Hayır", paragraf_no=None)
        save_reading_process("PRE_SPEED", speed, paragraf_no=None)

        st.session_state.phase = "during"
        st.rerun()

# =========================================================
# 4) DURING
# =========================================================
elif st.session_state.phase == "during":
    st.subheader("🟩 Okuma Sırası (DURING-READING)")
    st.markdown("<div class='fun-badge'>📖 2. Aşama: Şimdi okuma zamanı</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='mini-progress'>
        <div class='mini-progress-fill' style='width: 50%;'></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='section-soft-green'><b>Okuma Zamanı</b><br/>İstersen dinleyebilir, istersen tekrar okuyabilirsin.</div>", unsafe_allow_html=True)

    metin = st.session_state.activity.get("sade_metin", "Metin yok.")
    metin_hash = hash(metin)
    if st.session_state.get("metin_hash") != metin_hash:
        st.session_state.paragraphs = split_paragraphs(
            metin,
            target_min=500,
            target_max=800,
            tail_min=180
        )
        st.session_state.metin_hash = metin_hash

    paras = st.session_state.get("paragraphs", []) or []
    p_idx = st.session_state.get("p_idx", 0)
    total_paras = max(len(paras), 1)
    progress_ratio = p_idx / total_paras if total_paras else 0

    st.markdown(
        f"<div class='mini-success'>{get_motivation_message('during', progress_ratio)}</div>",
        unsafe_allow_html=True
    )

    render_badges()

    if p_idx < len(paras):
        c1, c2 = st.columns([2, 5])
        with c1:
            if st.button("🔊 Bu bölümü dinle"):
                st.session_state.repeat_count += 1
                st.session_state.tts_count += 1
                save_reading_process("TTS_PLAY", "Bölüm dinlendi", paragraf_no=p_idx + 1)
                fp = get_audio(paras[p_idx])
                if fp:
                    st.audio(fp, format="audio/mp3")
                    award_badge("🎧 Dinledim")

        with c2:
            st.markdown(
                f"<div class='small-note'>Seçtiğin hız: <b>{st.session_state.reading_speed}</b> | "
                f"Tekrar (dinleme+tekrar okuma): <b>{st.session_state.repeat_count}</b> | "
                f"Bölüm: <b>{min(p_idx+1, len(paras))}/{len(paras)}</b></div>",
                unsafe_allow_html=True
            )

        st.divider()
        st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)

        # Kelime desteği
        st.markdown("<div class='card'><b>🧩 Zor kelimeye yardım</b><br/>İstersen bölümden bir kelime seçip anlamını öğrenebilirsin.</div>", unsafe_allow_html=True)
        candidate_words = extract_candidate_words(paras[p_idx], min_len=6, max_count=12)
        if candidate_words:
            selected_word = st.selectbox("Kelime seç:", [""] + candidate_words, key=f"word_help_select_{p_idx}")
            if st.button("Kelimeyi Açıkla", key=f"word_help_btn_{p_idx}") and selected_word:
                try:
                    ans = explain_word_simple(selected_word, paras[p_idx])
                    st.session_state.last_word_help = selected_word
                    st.session_state.word_help_answer = ans
                    save_reading_process("WORD_HELP", f"{selected_word} | {ans}", paragraf_no=p_idx + 1)
                    award_badge("📘 Kelime Kâşifi")
                except Exception:
                    st.session_state.word_help_answer = "Bu kelimeyi şu an açıklayamadım."
        if st.session_state.get("word_help_answer"):
            st.info(f"🧠 {st.session_state.get('last_word_help','Kelime')}: {st.session_state.word_help_answer}")

        coln1, coln2 = st.columns(2)
        with coln1:
            if st.button("🔁 Bu bölümü tekrar oku", key=f"repeat_p_{p_idx}"):
                st.session_state.repeat_count += 1
                st.session_state.reread_count += 1
                save_reading_process("REPEAT_READ", "Bölüm tekrar okundu", paragraf_no=p_idx + 1)
                st.info("Tekrar okudun. Hazır olunca devam edebilirsin.")
                award_badge("🔁 Tekrar Okudum")
        with coln2:
            if st.button("➡️ Sonraki bölüm", key=f"next_p_{p_idx}"):
                if (p_idx + 1) >= len(paras):
                    award_badge("📖 Metni Bitirdim")
                st.session_state.p_idx = p_idx + 1
                st.rerun()
    else:
        st.markdown("<div class='mini-success'>🌟 Metni bitirdin! Şimdi önemli kısmı hatırlayalım.</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'><b>Metnin En Önemli Şeyi</b><br/>Sence bu metindeki en önemli şey neydi? (1 cümle)</div>", unsafe_allow_html=True)
        st.session_state.final_important_note = st.text_input("En önemli şey:", value=st.session_state.final_important_note)

        if st.button("📌 Kaydet (1 kez)"):
            if st.session_state.final_important_note.strip():
                if not st.session_state.final_important_saved:
                    st.session_state.final_important_saved = True
                    save_reading_process("IMPORTANT_NOTE_FINAL", st.session_state.final_important_note.strip(), paragraf_no=None)
                    st.success("Kaydedildi!")
                    award_badge("📌 Önemli Nokta Bulucu")
                else:
                    st.info("Zaten kaydedildi.")
            else:
                st.warning("Bir cümle yaz.")

        st.divider()
        st.markdown("<div class='card'><b>Ön Bilgi</b><br/>Bu metin sana daha önce yaşadığın/duyduğun bir şeyi hatırlattı mı?</div>", unsafe_allow_html=True)
        pk = st.text_area("Varsa kısaca yaz:", value=st.session_state.prior_knowledge, height=100)

        if st.button("Okuma Sonrasına Geç ➜"):
            st.session_state.prior_knowledge = pk.strip()
            save_reading_process("PRIOR_KNOWLEDGE", pk.strip() if pk.strip() else "(boş)", paragraf_no=None)
            st.session_state.phase = "post"
            st.rerun()

# =========================================================
# 5) POST
# =========================================================
elif st.session_state.phase == "post":
    st.subheader("🟧 Okuma Sonrası (POST-READING)")
    st.markdown("<div class='fun-badge'>🧠 3. Aşama: Düşünme ve toplama zamanı</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='mini-progress'>
        <div class='mini-progress-fill' style='width: 75%;'></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='section-soft-orange'><b>Toparlama Zamanı</b><br/>Şimdi metni hatırlayıp kendi cümlelerinle anlat.</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='mini-success'>{get_motivation_message('post')}</div>", unsafe_allow_html=True)

    metin = st.session_state.activity.get("sade_metin", "Metin yok.")
    render_badges()

    st.markdown("<div class='card'><b>Özetleme</b><br/>Metni 2–3 cümleyle anlat.</div>", unsafe_allow_html=True)

    voice_audio = st.audio_input("🎤 İstersen sesli anlat, ben yazıya çevireyim:", key="summary_audio")
    if voice_audio is not None:
        st.audio(voice_audio)
        if st.button("🎙️ Sesimi Yazıya Çevir", key="transcribe_summary_btn"):
            text = transcribe_audio_bytes(voice_audio.getvalue())
            if text:
                st.session_state.summary = text
                st.session_state.voice_text = text
                save_reading_process("VOICE_TO_TEXT", text, paragraf_no=None)
                award_badge("🎤 Sesli Yanıt")
                st.success("Sesin yazıya çevrildi.")
            else:
                st.warning("Ses şu anda yazıya çevrilemedi.")

    if st.session_state.get("voice_text"):
        st.info(f"📝 Sesli yanıt metni: {st.session_state.voice_text}")

    summ = st.text_area("Özetin:", value=st.session_state.summary, height=120)

    if st.button("Özeti Kaydet ✅"):
        st.session_state.summary = summ.strip()
        if st.session_state.summary:
            save_reading_process("POST_SUMMARY", st.session_state.summary, paragraf_no=None)
            try:
                fb = generate_summary_feedback(metin, st.session_state.summary)
                st.session_state.summary_feedback = fb
                save_reading_process("AI_SUMMARY_FEEDBACK", fb, paragraf_no=None)
                award_badge("📝 Özet Ustası")
            except Exception:
                st.session_state.summary_feedback = ""
        st.success("✅ Özet kaydedildi!")

    if st.session_state.get("summary_feedback"):
        st.info(f"🤖 Chatbot geri bildirimi: {st.session_state.summary_feedback}")

    st.divider()
    st.subheader("🧠 Kendimi Değerlendiriyorum (Kısa)")

    st.markdown("<div class='card'><b>Okurken zorlandığımda ne yaptım?</b><br/>1 cümle yaz.</div>", unsafe_allow_html=True)
    r1 = st.text_input("Stratejim:", value=st.session_state.get("reflection_strategy", ""))

    st.markdown("<div class='card'><b>Bir dahaki metinde neyi farklı yapacağım?</b><br/>1 cümle yaz.</div>", unsafe_allow_html=True)
    r2 = st.text_input("Bir dahaki sefere:", value=st.session_state.get("reflection_next_time", ""))

    if st.button("Kısa değerlendirmeyi kaydet ✅"):
        st.session_state.reflection_strategy = (r1 or "").strip()
        st.session_state.reflection_next_time = (r2 or "").strip()
        save_reading_process("POST_REFLECTION_STRATEGY", st.session_state.reflection_strategy or "(boş)", paragraf_no=None)
        save_reading_process("POST_REFLECTION_NEXT", st.session_state.reflection_next_time or "(boş)", paragraf_no=None)
        st.success("✅ Kaydedildi!")
        award_badge("🧠 Düşünen Okuyucu")

    st.divider()
    st.subheader("🗺️ Öykü Haritası (Story Map)")
    st.markdown("""
    <div class='card'><b>Nasıl dolduracaksın?</b><br/>
    Metindeki öykünün parçalarını tek tek yaz. Kısa yazman yeterli (1–2 cümle).</div>
    """, unsafe_allow_html=True)

    templates = get_storymap_templates()
    st.markdown("<div class='small-note'>Zorlanırsan aşağıdaki başlangıç cümlelerini kullanabilirsin.</div>", unsafe_allow_html=True)

    sm = st.session_state.story_map
    col1, col2 = st.columns(2)
    with col1:
        sm["kahraman"] = st.text_input("👤 Kahraman", value=sm["kahraman"], placeholder=templates["kahraman"])
        sm["mekan"] = st.text_input("🏠 Mekân", value=sm["mekan"], placeholder=templates["mekan"])
        sm["zaman"] = st.text_input("🕒 Zaman", value=sm["zaman"], placeholder=templates["zaman"])
    with col2:
        sm["problem"] = st.text_input("⚠️ Problem", value=sm["problem"], placeholder=templates["problem"])
        sm["olaylar"] = st.text_area("🔁 Olaylar", value=sm["olaylar"], height=110, placeholder=templates["olaylar"])
        sm["cozum"] = st.text_input("✅ Çözüm", value=sm["cozum"], placeholder=templates["cozum"])

    st.session_state.story_map = sm

    col_a, col_b = st.columns([2, 1])
    with col_a:
        if st.button("🗂️ Öykü Haritasını Kaydet ve PUANLA (AI)"):
            filled = sum(1 for _, v in sm.items() if str(v).strip())
            st.session_state.story_map_filled = filled
            if filled < 3:
                st.warning("En az 3 alanı doldur (ör. kahraman, mekân, problem).")
            else:
                with st.spinner("AI rubrik puanı hesaplanıyor..."):
                    scores, total, reason = ai_score_story_map(metin, sm)
                ok = save_story_map_row(sm, scores, total, reason)
                if ok:
                    st.session_state.story_map_ai_scored = True
                    st.session_state.story_map_last_total = total
                    st.session_state.story_map_last_reason = reason
                    save_reading_process("STORY_MAP_SCORED", f"{total}/12 | {reason}", paragraf_no=None)

                    try:
                        sm_fb = generate_storymap_feedback(metin, sm)
                        st.session_state.storymap_feedback = sm_fb
                        save_reading_process("AI_STORYMAP_FEEDBACK", sm_fb, paragraf_no=None)
                    except Exception:
                        st.session_state.storymap_feedback = ""

                    st.success(f"✅ Kaydedildi! AI Puan: {total}/12")
                    st.caption(f"Gerekçe: {reason}")
                    award_badge("🗺️ Öykü Haritası Tamamlandı")

    with col_b:
        st.markdown(
            "<div class='small-note'>AI Puan: ✅</div>" if st.session_state.story_map_ai_scored
            else "<div class='small-note'>AI Puan: ⏳</div>",
            unsafe_allow_html=True
        )

    if st.session_state.get("storymap_feedback"):
        st.info(f"🤖 Chatbot yorumu: {st.session_state.storymap_feedback}")

    st.divider()
    st.subheader("🤖 Okuma Dostum ile Konuş")

    chat_container = st.container()
    with chat_container:
        if st.session_state.get("chat_messages"):
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    st.markdown(f"<div class='chat-user'><b>Sen:</b><br/>{msg['content']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='chat-bot'><b>Okuma Dostum:</b><br/>{msg['content']}</div>", unsafe_allow_html=True)

    st.divider()

    user_msg = st.text_input("Metinle ilgili bir şey sor veya yardım iste:", key="chat_input_post")

    if st.button("Gönder", key="send_chat_post") and user_msg.strip():
        try:
            reply = chat_about_text(
                metin=metin,
                user_message=user_msg.strip(),
                chat_history=st.session_state.get("chat_messages", [])
            )
            st.session_state.chat_messages.append({"role": "user", "content": user_msg.strip()})
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            save_reading_process("CHAT_USER", user_msg.strip(), paragraf_no=None)
            save_reading_process("CHATBOT_REPLY", reply, paragraf_no=None)
            award_badge("💬 Chatbotla Konuştum")
            st.rerun()
        except Exception:
            st.warning("Şu anda chatbot yanıtı üretilemedi.")

    if st.button("Sorulara Geç ➜"):
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 6) QUESTIONS
# =========================================================
elif st.session_state.phase == "questions":
    sorular = st.session_state.activity.get("sorular", [])
    i = st.session_state.get("q_idx", 0)
    total_q = len(sorular)

    if not sorular:
        st.error("Sorular bulunamadı. SoruBankasi'nda bu metin için soru olmalı.")
        st.stop()

    metin = st.session_state.activity.get("sade_metin", "")
    opts = st.session_state.activity.get("opts") or option_letters_for_metin(st.session_state.get("metin_id", ""))

    if "show_text_in_questions" not in st.session_state:
        st.session_state.show_text_in_questions = False

    st.markdown("<div class='fun-badge'>⭐ 4. Aşama: Soruları çözüyoruz</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='mini-progress'>
        <div class='mini-progress-fill' style='width: 95%;'></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<div class='mini-success'>{get_motivation_message('questions')}</div>", unsafe_allow_html=True)
    render_badges()

    colt1, colt2 = st.columns([3, 1])
    with colt1:
        st.markdown("<div class='small-note'>İstersen sorularda metni buradan açıp okuyabilirsin.</div>", unsafe_allow_html=True)
    with colt2:
        if st.button("📄 Metni Göster / Gizle"):
            st.session_state.show_text_in_questions = not st.session_state.show_text_in_questions

    if st.session_state.show_text_in_questions:
        with st.expander("📄 Metin", expanded=True):
            st.write(metin)

    st.divider()

    if i < total_q:
        q = sorular[i]
        current_hint_level = st.session_state.hint_level_by_q.get(i, 0)

        st.subheader(f"Soru {i+1} / {total_q}")
        st.markdown(
            f"<div class='small-note'>İpucu seviyesi: <b>{current_hint_level}</b>/3</div>",
            unsafe_allow_html=True
        )
        st.markdown(f"<div style='font-size:22px; margin-bottom:14px;'>{q.get('kok','')}</div>", unsafe_allow_html=True)

        for opt in opts:
            if st.button(f"{opt}) {q.get(opt,'')}", key=f"q_{i}_{opt}"):
                st.session_state.question_attempts[i] = st.session_state.question_attempts.get(i, 0) + 1
                is_correct = (opt == q.get("dogru"))
                st.session_state.correct_map[i] = 1 if is_correct else 0

                save_reading_process(
                    "ANSWER",
                    f"Soru {i+1} | secim={opt} | dogru={q.get('dogru')} | dogru_mu={is_correct} | deneme={st.session_state.question_attempts[i]}",
                    paragraf_no=None
                )

                if is_correct:
                    st.success("🌟 Doğru!")
                    st.session_state.ai_hint_text = ""
                    if current_hint_level == 0:
                        award_badge("🏅 İpucusuz Doğru")
                    else:
                        award_badge("💡 İpucuyla Başardım")
                    st.session_state.q_idx = i + 1
                    st.rerun()
                else:
                    st.error("Tekrar dene!")
                    try:
                        next_level = min(st.session_state.hint_level_by_q.get(i, 0) + 1, 3)
                        st.session_state.hint_level_by_q[i] = next_level

                        ai_hint = generate_ai_hint(metin, q, opt, level=next_level)
                        st.session_state.ai_hint_text = f"(İpucu {next_level}) {ai_hint}"

                        save_reading_process(
                            "AI_HINT_AUTO",
                            f"Soru {i+1} | seviye={next_level} | {ai_hint}",
                            paragraf_no=None
                        )
                    except Exception:
                        st.session_state.ai_hint_text = "Metinde bu soruyla ilgili bölümü tekrar incele."

        if st.session_state.get("ai_hint_text"):
            st.info(f"🤖 Chatbot ipucu: {st.session_state.ai_hint_text}")

        if st.button("💡 İpucu Al", key=f"hint_{i}"):
            st.session_state.hints += 1
            st.session_state.show_text_in_questions = True

            next_level = min(st.session_state.hint_level_by_q.get(i, 0) + 1, 3)
            st.session_state.hint_level_by_q[i] = next_level

            save_reading_process(
                "HINT",
                f"Soru {i+1} | ipucu_alindi | seviye={next_level}",
                paragraf_no=None
            )

            try:
                ai_hint = generate_ai_hint(metin, q, "İpucu istendi", level=next_level)
                st.session_state.ai_hint_text = f"(İpucu {next_level}) {ai_hint}"
                save_reading_process(
                    "AI_HINT_MANUAL",
                    f"Soru {i+1} | seviye={next_level} | {ai_hint}",
                    paragraf_no=None
                )
                st.info(f"🤖 Chatbot ipucu: (İpucu {next_level}) {ai_hint}")
                award_badge("💡 İpucu Kullandım")
            except Exception:
                st.info("📌 Metni açtım. Anahtar kelimeleri metinde ara ve ilgili bölümü tekrar oku.")

    else:
        if not st.session_state.saved_perf:
            dogru = sum(st.session_state.correct_map.values())
            sure = round((time.time() - st.session_state.start_t) / 60, 2)

            wrongs = [str(idx + 1) for idx, v in st.session_state.correct_map.items() if v == 0]
            hatali = "Yanlış: " + ",".join(wrongs) if wrongs else "Hepsi doğru"

            tahmin = st.session_state.get("prediction", "")
            dikkat = "Evet" if st.session_state.get("attention_ok", False) else "Hayır"
            hiz = st.session_state.get("reading_speed", "")

            final_note = (st.session_state.get("final_important_note", "") or "").strip()
            onemli_not_sayisi = 1 if final_note else 0
            prior_var = 1 if (st.session_state.get("prior_knowledge", "") or "").strip() else 0

            basari_yuzde = f"%{round((dogru/total_q)*100, 1)}" if total_q else "%0"

            row = [
                st.session_state.session_id,
                st.session_state.user,
                st.session_state.login_time,
                sure,
                "",
                basari_yuzde,
                total_q,
                dogru,
                hatali,
                st.session_state.metin_id,
                st.session_state.hints,
                "Evet",
                "Evet",
                0,
                0,
                tahmin,
                dikkat,
                hiz,
                st.session_state.get("repeat_count", 0),
                st.session_state.get("tts_count", 0),
                st.session_state.get("reread_count", 0),
                onemli_not_sayisi,
                prior_var,
            ]

            ok = append_row_safe("Performans", row)
            if ok:
                if dogru == total_q and total_q > 0:
                    award_badge("🏆 Tüm Sorular Doğru")
                if st.session_state.get("hints", 0) == 0:
                    award_badge("🌟 İpucusuz Tamamlama")

                st.session_state.last_report = {
                    "basari_yuzde": basari_yuzde,
                    "dogru": dogru,
                    "total_q": total_q,
                    "sure_dk": sure,
                    "hints": int(st.session_state.get("hints", 0)),
                    "prediction": (st.session_state.get("prediction", "") or "").strip(),
                    "attention": "Evet" if st.session_state.get("attention_ok", False) else "Hayır",
                    "speed": st.session_state.get("reading_speed", ""),
                    "repeat_count": int(st.session_state.get("repeat_count", 0)),
                    "tts_count": int(st.session_state.get("tts_count", 0)),
                    "reread_count": int(st.session_state.get("reread_count", 0)),
                    "important_note": (st.session_state.get("final_important_note", "") or "").strip(),
                    "prior_knowledge": (st.session_state.get("prior_knowledge", "") or "").strip(),
                    "summary": (st.session_state.get("summary", "") or "").strip(),
                }

                try:
                    sig = compute_metacog_signals()
                    scores = rule_based_metacog_score(sig)
                    save_metacog_rubric_row(scores, scores.get("reason", ""), sig)
                    save_reading_process("METACOG_RUBRIC_SAVED", f"total={scores.get('total',0)}", paragraf_no=None)
                except Exception:
                    save_reading_process("METACOG_RUBRIC_ERROR", traceback.format_exc()[:2000], paragraf_no=None)

                save_reading_process("SESSION_END", f"Performans kaydedildi | dogru={dogru}/{total_q} | sure={sure}dk", paragraf_no=None)
                st.session_state.saved_perf = True
                st.session_state.phase = "done"
                st.rerun()

# =========================================================
# 7) DONE
# =========================================================
elif st.session_state.phase == "done":
    st.balloons()
    st.success("✅ Bugünkü çalışman kaydedildi!")
    st.markdown("<div class='fun-badge'>🏆 Tebrikler! Bugünkü görevi tamamladın</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='mini-progress'>
        <div class='mini-progress-fill' style='width: 100%;'></div>
    </div>
    """, unsafe_allow_html=True)

    rep = st.session_state.get("last_report", {}) or {}
    render_badges()

    if rep:
        st.subheader("📊 Bugünkü Skor Özeti")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='card'><b>Başarı</b><br/>{rep.get('basari_yuzde','')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>Doğru</b><br/>{rep.get('dogru',0)}/{rep.get('total_q',0)}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card'><b>Süre</b><br/>{rep.get('sure_dk',0)} dk</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>İpucu</b><br/>{rep.get('hints',0)}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='card'><b>Tekrar</b><br/>{rep.get('repeat_count',0)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>Dinleme (TTS)</b><br/>{rep.get('tts_count',0)}</div>", unsafe_allow_html=True)

        st.markdown(f"<div class='card'><b>Tahmin</b><br/>{rep.get('prediction','(boş)') or '(boş)'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card'><b>Dikkat</b><br/>{rep.get('attention','')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card'><b>Okuma Hızı</b><br/>{rep.get('speed','')}</div>", unsafe_allow_html=True)

        if rep.get("important_note"):
            st.markdown(f"<div class='card'><b>Metnin En Önemli Şeyi</b><br/>{rep.get('important_note')}</div>", unsafe_allow_html=True)
        if rep.get("prior_knowledge"):
            st.markdown(f"<div class='card'><b>Ön Bilgi (Ne bildi?)</b><br/>{rep.get('prior_knowledge')}</div>", unsafe_allow_html=True)
        if rep.get("summary"):
            st.markdown(f"<div class='card'><b>Özet</b><br/>{rep.get('summary')}</div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("📈 Grafikte Bugün Ne Yaptım?")
        wrong = max(int(rep.get("total_q", 0)) - int(rep.get("dogru", 0)), 0)
        df = pd.DataFrame(
            {
                "Değer": [
                    float(rep.get("sure_dk", 0)),
                    int(rep.get("dogru", 0)),
                    int(wrong),
                    int(rep.get("hints", 0)),
                    int(rep.get("repeat_count", 0)),
                    int(rep.get("tts_count", 0)),
                    int(rep.get("reread_count", 0)),
                ]
            },
            index=[
                "Süre (dk)",
                "Doğru",
                "Yanlış",
                "İpucu",
                "Tekrar (toplam)",
                "Dinleme (TTS)",
                "Tekrar Okuma",
            ],
        )
        st.bar_chart(df)

    st.divider()
    st.subheader("🗺️ Öykü Haritası Sonucun")
    sm = st.session_state.get("story_map", {}) or {}
    st.markdown(f"<div class='card'><b>👤 Kahraman</b><br/>{(sm.get('kahraman') or '(boş)')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><b>🏠 Mekân</b><br/>{(sm.get('mekan') or '(boş)')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><b>🕒 Zaman</b><br/>{(sm.get('zaman') or '(boş)')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><b>⚠️ Problem</b><br/>{(sm.get('problem') or '(boş)')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><b>🔁 Olaylar</b><br/>{(sm.get('olaylar') or '(boş)')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><b>✅ Çözüm</b><br/>{(sm.get('cozum') or '(boş)')}</div>", unsafe_allow_html=True)

    sm_total = st.session_state.get("story_map_last_total")
    sm_reason = st.session_state.get("story_map_last_reason", "")
    if sm_total is not None:
        st.info(f"🗺️ Öykü Haritası (AI) Puanın: {sm_total}/12")
        if sm_reason:
            st.caption(f"Gerekçe: {sm_reason}")

    if st.session_state.get("summary_feedback"):
        st.markdown(f"<div class='card'><b>🤖 Özet Geri Bildirimi</b><br/>{st.session_state.get('summary_feedback')}</div>", unsafe_allow_html=True)

    if st.session_state.get("storymap_feedback"):
        st.markdown(f"<div class='card'><b>🤖 Öykü Haritası Yorumu</b><br/>{st.session_state.get('storymap_feedback')}</div>", unsafe_allow_html=True)

    st.divider()
    if st.button("Yeni Metin"):
        st.session_state.phase = "auth"
        st.session_state.metin_id = ""
        reset_activity_states()
        st.rerun()
    if st.button("Çıkış"):
        st.session_state.clear()
        st.rerun()
