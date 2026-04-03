
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
# OKUMA DOSTUM — ÖÖG UYUMLU TAM SÜRÜM
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Lexend', sans-serif;
    font-size: 19px;
    background: linear-gradient(180deg, #f7fbff 0%, #fffdf7 100%);
  }

  .main {
    background: linear-gradient(180deg, #f7fbff 0%, #fffdf7 100%);
  }

  h1, h2, h3 {
    color: #243447;
    letter-spacing: 0.2px;
  }

  .stButton button {
    width: 100%;
    border-radius: 16px;
    height: 3em;
    font-weight: 800;
    font-size: 17px !important;
    border: 1px solid #2f80ed;
    background: linear-gradient(90deg, #2f80ed 0%, #56ccf2 100%);
    color: white;
    box-shadow: 0 6px 14px rgba(47, 128, 237, 0.18);
    transition: all 0.15s ease-in-out;
  }

  .stButton button:hover {
    transform: translateY(-1px);
    filter: brightness(1.02);
  }

  .hero-box {
    background: linear-gradient(135deg, #fff8e8 0%, #eef7ff 100%);
    border: 2px solid #e3eefc;
    border-radius: 28px;
    padding: 28px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.06);
    margin-bottom: 18px;
    text-align: center;
  }

  .hero-title {
    font-size: 38px;
    font-weight: 800;
    color: #234;
    margin-bottom: 10px;
  }

  .hero-sub {
    font-size: 18px;
    color: #4f5d6b;
    line-height: 1.7;
  }

  .emoji-row {
    font-size: 54px;
    text-align: center;
    margin-bottom: 14px;
    letter-spacing: 8px;
  }

  .info-pill {
    background: #ffffff;
    border: 1px solid #ddeafb;
    border-radius: 16px;
    padding: 12px 14px;
    margin-bottom: 10px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.03);
    font-size: 16px;
  }

  .highlight-box {
    background: #ffffff;
    padding: 22px;
    border-radius: 18px;
    box-shadow: 0 6px 16px rgba(0,0,0,0.05);
    border-left: 8px solid #ffd54f;
    font-size: 22px !important;
    line-height: 1.9 !important;
    margin-bottom: 16px;
    white-space: pre-wrap;
  }

  .small-note {
    color: #4f5d6b;
    font-size: 15px;
    background: #eef5ff;
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid #d8e8ff;
    margin-bottom: 8px;
  }

  .card {
    background: #ffffff;
    padding: 16px;
    border-radius: 16px;
    border: 1px solid #e7eef7;
    margin-bottom: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
  }

  .mini-success {
    background: #eaf7ee;
    color: #245c36;
    padding: 10px 12px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 600;
    margin: 8px 0 12px 0;
  }

  div[data-testid="stTextInput"] input,
  div[data-testid="stTextArea"] textarea {
    border-radius: 14px !important;
    border: 2px solid #dfe8f3 !important;
    background: #ffffff !important;
    box-shadow: none !important;
    font-size: 17px !important;
  }

  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stTextArea"] textarea:focus {
    border: 2px solid #9ecbff !important;
    box-shadow: 0 0 0 2px rgba(158, 203, 255, 0.18) !important;
  }

  div[data-testid="stRadio"] label,
  div[data-testid="stCheckbox"] label {
    font-size: 17px !important;
  }

  .stAlert {
    border-radius: 14px !important;
  }

  section[data-testid="stSidebar"] {
    display: none !important;
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

def go_to_phase(target_phase: str):
    st.session_state.phase = target_phase
    st.rerun()

def top_back_button(target_phase: str, label: str = "⬅️ Geri"):
    col_a, col_b = st.columns([8, 1])
    with col_b:
        if st.button(label, key=f"top_back_{target_phase}_{st.session_state.get('phase','')}"):
            go_to_phase(target_phase)

def maybe_log_once(key: str, kayit_turu: str, value: str, paragraf_no=None):
    value = str(value or "").strip()
    cache = st.session_state.get("autosave_cache", {}) or {}
    if cache.get(key) != value:
        cache[key] = value
        st.session_state.autosave_cache = cache
        save_reading_process(kayit_turu, value if value else "(boş)", paragraf_no=paragraf_no)

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

def _safe_sentence_cut(text: str, target: int) -> int:
    if not text:
        return 0

    left = max(0, target - 250)
    right = min(len(text), target + 250)

    for marker in [". ", "! ", "? ", ".\n", "!\n", "?\n", ".\"", "!\"", "?\""]:
        pos = text.rfind(marker, left, right)
        if pos != -1:
            return pos + 1

    pos = text.rfind(", ", left, right)
    if pos != -1:
        return pos + 1

    pos = text.rfind(" ", left, right)
    if pos != -1:
        return pos

    return target

def _split_single_block_to_n_parts(text: str, n: int):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []

    if n <= 1:
        return [text]

    if n == 2:
        cut1 = _safe_sentence_cut(text, len(text) // 2)
        return [text[:cut1].strip(), text[cut1:].strip()]

    cut1 = _safe_sentence_cut(text, len(text) // 3)
    cut2 = _safe_sentence_cut(text, (len(text) * 2) // 3)

    if cut2 <= cut1:
        cut2 = _safe_sentence_cut(text, cut1 + (len(text) - cut1) // 2)

    parts = [
        text[:cut1].strip(),
        text[cut1:cut2].strip(),
        text[cut2:].strip()
    ]
    return [p for p in parts if p]

def split_paragraphs(text: str):
    text = (text or "").strip()
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?]) +', text)

    if len(sentences) < 6:
        return [" ".join(sentences)]

    elif len(sentences) < 12:
        mid = len(sentences)//2
        return [" ".join(sentences[:mid]), " ".join(sentences[mid:])]

    else:
        third = len(sentences)//3
        return [
            " ".join(sentences[:third]),
            " ".join(sentences[third:2*third]),
            " ".join(sentences[2*third:])
        ]
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
        return (getattr(resp, "text", "") or "").strip()
    except Exception:
        try:
            bio = BytesIO(audio_bytes)
            bio.name = "speech.wav"
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=bio
            )
            return (getattr(resp, "text", "") or "").strip()
        except Exception:
            return ""

# =========================================================
# CHATBOT / FEEDBACK
# =========================================================
def generate_ai_hint(metin: str, soru: dict, wrong_choice: str, level: int = 1):
    opts_payload = {}
    for k in ["A", "B", "C", "D"]:
        if soru.get(k):
            opts_payload[k] = soru.get(k)

    if level == 1:
        level_instruction = """
- Çok kısa ve genel bir ipucu ver.
- Öğrenciyi metindeki ilgili bölüme yönlendir.
- Cevabı söyleme.
"""
    elif level == 2:
        level_instruction = """
- Biraz daha açık ipucu ver.
- Yine cevabı söyleme.
- Dikkat etmesi gereken kelime ya da cümleyi sezdir.
"""
    else:
        level_instruction = """
- En açık ipucunu ver.
- Ama doğru seçeneği doğrudan söyleme.
- Öğrenciyi cevaba çok yaklaştır.
"""

    sys = f"""
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine destek olan sabırlı bir okuma öğretmenisin.

Kurallar:
- Türkçe yaz.
- Kısa yaz.
- En fazla 2 kısa cümle kullan.
- Zor kelime kullanma.
- Karmaşık cümle kurma.
- Cevabı doğrudan verme.
- Öğrenciyi korkutma, yargılama.
- Nazik ve destekleyici ol.
- Metindeki ilgili yere yönlendir.
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
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine destek olan bir öğretmensin.

Kurallar:
- Türkçe yaz.
- Çok kısa yaz.
- En fazla 3 kısa cümle yaz.
- Önce öğrencinin iyi yaptığı bir şeyi söyle.
- Sonra sadece 1 küçük geliştirme önerisi ver.
- Sade ve anlaşılır kelimeler kullan.
- Nazik ve destekleyici ol.
"""
    payload = {
        "metin": (metin or "")[:2500],
        "ogrenci_ozeti": (ozet or "")[:1000]
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.3)
    return resp.choices[0].message.content.strip()

def generate_storymap_feedback(metin: str, sm: dict):
    sys = """
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine destek olan bir öğretmensin.

Kurallar:
- Türkçe yaz.
- Çok kısa yaz.
- En fazla 3 kısa cümle kullan.
- Öğrencinin doğru yaptığı bir şeyi söyle.
- Sonra sadece 1 kısa öneri ver.
- Cevabı doğrudan verme.
- Nazik ve motive edici ol.
"""
    payload = {
        "metin": (metin or "")[:2500],
        "story_map": sm
    }
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False), temperature=0.3)
    return resp.choices[0].message.content.strip()

def explain_word_simple(word: str, metin: str):
    sys = """
Sen özel öğrenme güçlüğü yaşayan ortaokul öğrencilerine kelime açıklayan sabırlı bir öğretmensin.

Kurallar:
- Türkçe yaz.
- Çok basit anlat.
- En fazla 2 kısa cümle kullan.
- Zor kelime kullanma.
- Gerekirse metindeki anlama göre açıkla.
- Kısa ve net ol.
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
    raise ValueError(f"Sheet sekmesi bulunamadı: '{sheet_name}'.")

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
# LOG
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
        "attention_ok": False,
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
    plan = 1 if sig["prediction_len"] >= 5 else 0

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
    reason = "Kural tabanlı rubrik."
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
# BANKA
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
        for c in [L.lower(), L.lower().strip(), L.strip().lower()]:
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
        diag = f"Bulunan soru={len(sorular)} / Beklenen={exp_n}."
        return None, diag

    return {"sade_metin": metin, "baslik": baslik, "pre_ipucu": pre_ipucu, "sorular": sorular, "opts": opts}, ""

# =========================================================
# STORY MAP AI
# =========================================================
def _tr_lower_story(s: str) -> str:
    s = str(s or "")
    repl = str.maketrans({"I": "ı", "İ": "i", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
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
        "cozum": ["sonuc", "sonuç", "care", "çare"],
        "mutlu": ["sevindi", "sevincli", "sevinçli", "mutluydu"],
        "korktu": ["ürktü", "urktu", "endiselendi", "endişelendi"],
        "arkadas": ["dost", "arkadaşı", "arkadasi"],
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
    return best_sent if len(words) <= max_words else " ".join(words[:max_words])

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

    sys = f"""
Sen özel öğrenme güçlüğü yaşayan öğrencilerin öykü haritası cevaplarını dikkatli değerlendiren bir öğretmensin.

Alan: {field_name}

0 puan: yanlış / alakasız
1 puan: kısmen doğru
2 puan: doğru veya kabul edilebilir eş anlamlı

Sadece JSON üret:
{{"score":0,"evidence":"","reason":""}}
"""
    user = json.dumps({"alan": field_name, "ogrenci_cevabi": answer, "metin": (metin or "")[:5000]}, ensure_ascii=False)
    try:
        resp = openai_json_request(sys, user, model="gpt-4o-mini", temperature=0)
        data = json.loads(resp.choices[0].message.content)
        score = max(0, min(2, int(data.get("score", 0))))
        evidence = str(data.get("evidence", "") or "").strip()[:180]
        reason = str(data.get("reason", "") or "").strip()[:160]
        return score, evidence, reason
    except Exception:
        return 0, "", "LLM puanı alınamadı"

def ai_score_story_map(metin: str, sm: dict):
    alanlar = ["kahraman", "mekan", "zaman", "problem", "olaylar", "cozum"]
    kural_agirlikli = {"kahraman", "mekan", "zaman"}
    out, reasons = {}, {}

    for key in alanlar:
        answer = sm.get(key, "")
        rule_score, _, rule_reason = _score_single_story_field_rule(answer, metin, key)

        if key in kural_agirlikli:
            out[key] = int(rule_score)
            reasons[key] = rule_reason
            continue

        if not str(answer or "").strip():
            out[key] = 0
            reasons[key] = "Boş cevap"
            continue

        llm_score, _, llm_reason = _llm_semantic_score(key, answer, metin)
        out[key] = int(max(rule_score, llm_score))
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
    return out, total, reason[:220]

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
# STATE
# =========================================================
def reset_activity_states():
    st.session_state.saved_perf = False
    st.session_state.busy = False

    st.session_state.prediction = ""
    st.session_state.reading_speed = ""

    st.session_state.repeat_count = 0
    st.session_state.tts_count = 0
    st.session_state.reread_count = 0

    st.session_state.final_important_note = ""
    st.session_state.prior_knowledge = ""
    st.session_state.summary = ""

    st.session_state.story_map = {
        "kahraman": "",
        "mekan": "",
        "zaman": "",
        "problem": "",
        "olaylar": "",
        "cozum": ""
    }
    st.session_state.story_map_ai_scored = False
    st.session_state.story_map_last_total = None
    st.session_state.story_map_last_reason = ""
    st.session_state.story_map_filled = 0

    st.session_state.hint_level_by_q = {}
    st.session_state.question_attempts = {}
    st.session_state.show_text_in_questions = False
    st.session_state.show_text_button_after_hint = False
    st.session_state.last_question_seen = -1
    st.session_state.question_status = {}
    st.session_state.correct_map = {}
    st.session_state.skipped_questions = []
    st.session_state.question_feedback = {}
    st.session_state.q_idx = 0

    st.session_state.reflection_has_difficulty = ""
    st.session_state.reflection_strategy = ""
    st.session_state.reflection_next_time = ""

    st.session_state.last_report = {}
    st.session_state.ai_hint_text = ""
    st.session_state.summary_feedback = ""
    st.session_state.storymap_feedback = ""
    st.session_state.last_word_help = ""
    st.session_state.word_help_answer = ""
    st.session_state.autosave_cache = {}
    st.session_state.voice_text = ""
    st.session_state.summary_feedback_done = False

if "phase" not in st.session_state:
    st.session_state.phase = "auth"
if "busy" not in st.session_state:
    st.session_state.busy = False

if st.session_state.phase != "auth":
    col_a, col_b = st.columns([9, 1])
    with col_b:
        if st.button("Çıkış"):
            st.session_state.clear()
            st.rerun()

# =========================================================
# 1) AUTH
# =========================================================
if st.session_state.phase == "auth":
    st.markdown("<div class='emoji-row'>📚 ✨ 🧠 🌈 📖</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="hero-box">
        <div class="hero-title">Okuma Dostum</div>
        <div class="hero-sub">
            Birlikte okuyalım, düşünelim ve soruları çözelim.<br>
            Hazırsan öğrenci kodunu yaz ve metnini seç.
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='info-pill'>📖 Metni okuyacaksın</div>", unsafe_allow_html=True)
        st.markdown("<div class='info-pill'>🧩 Bilmediğin kelimeyi sorabileceksin</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='info-pill'>❓ Soruları çözeceksin</div>", unsafe_allow_html=True)
        st.markdown("<div class='info-pill'>🗺️ Öykü haritası oluşturacaksın</div>", unsafe_allow_html=True)

    u = st.text_input("Öğrenci Kodun")

    try:
        metin_ids_all = list_metin_ids()
    except Exception:
        metin_ids_all = []
        st.error("❌ MetinBankasi okunamadı.")
        st.code(traceback.format_exc())

    selected_id = st.selectbox("Metin seç", metin_ids_all) if metin_ids_all else st.text_input("Metin ID", "Metin_001")

    if st.button("Başlayalım"):
        if not u or not selected_id:
            st.warning("Lütfen öğrenci kodunu yaz ve bir metin seç.")
        else:
            st.session_state.user = u
            st.session_state.metin_id = selected_id
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
            reset_activity_states()

            activity, err = load_activity_from_bank(selected_id)
            if activity is None:
                st.error(f"❌ Yüklenemedi: {err}")
                st.stop()

            st.session_state.activity = activity
            st.session_state.paragraphs = split_paragraphs(activity.get("sade_metin", ""))
            st.session_state.p_idx = 0
            st.session_state.hints = 0
            st.session_state.start_t = time.time()
            st.session_state.saved_perf = False

            save_reading_process("SESSION_START", f"Metin yüklendi: {selected_id}", paragraf_no=None)

            st.session_state.phase = "pre"
            st.rerun()

# =========================================================
# 2) PRE
# =========================================================
elif st.session_state.phase == "pre":
    top_back_button("auth")

    st.subheader("Okuma Öncesi")

    baslik = st.session_state.activity.get("baslik", "")
    pre_ipucu = st.session_state.activity.get("pre_ipucu", "")

    if baslik:
        st.markdown(f"<div class='card'><b>Metnin Başlığı</b><br/>{baslik}</div>", unsafe_allow_html=True)
    if pre_ipucu:
        st.markdown(f"<div class='small-note'>{pre_ipucu}</div>", unsafe_allow_html=True)

    curiosity = st.text_input("Sence bu metin ne hakkında olabilir?", value=st.session_state.prediction)

    speed = st.radio(
        "Okuma hızını seç",
        ["Yavaş", "Orta", "Hızlı"],
        index=None,
        key="reading_speed_radio_pre"
    )

    st.session_state.prediction = curiosity.strip()
    st.session_state.reading_speed = speed if speed else ""

    maybe_log_once("pre_prediction", "PRE_PREDICTION_AUTO", st.session_state.prediction, paragraf_no=None)
    maybe_log_once("pre_speed", "PRE_SPEED_AUTO", st.session_state.reading_speed, paragraf_no=None)

    if st.button("Metne Geç"):
        if not st.session_state.reading_speed:
            st.warning("Lütfen önce okuma hızını seç.")
        else:
            st.session_state.phase = "during"
            st.rerun()

# =========================================================
# 3) DURING
# =========================================================
elif st.session_state.phase == "during":

    st.subheader("Metin")

    metin = st.session_state.activity.get("sade_metin", "")

    if "paragraphs" not in st.session_state or not st.session_state.paragraphs:
        st.session_state.paragraphs = split_paragraphs(metin)

    parts = st.session_state.paragraphs
    p_idx = st.session_state.get("p_idx", 0)
    total_parts = len(parts)

    st.write(f"Bölüm {p_idx+1} / {total_parts}")

    # 🔊 Dinleme / 🔁 Tekrar
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔊 Dinle"):
            fp = get_audio(parts[p_idx])
            if fp:
                st.audio(fp, format="audio/mp3")

    with col2:
        if st.button("🔁 Tekrar Oku"):
            st.info("Bu bölümü tekrar okuyabilirsin.")

    # 📖 Metin
    st.write(parts[p_idx])

    st.divider()

    # ⬅️ ➡️ Navigasyon
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Önceki", disabled=(p_idx == 0)):
            st.session_state.p_idx = max(0, p_idx - 1)
            st.rerun()

    with col2:
        if st.button("➡️ Sonraki"):
            if p_idx < total_parts - 1:
                st.session_state.p_idx = p_idx + 1
                st.rerun()
            else:
                # ❗ buton içinde buton yok → direkt geçiş
                st.session_state.phase = "questions"
                st.rerun()
# =========================================================
# 4) POST
# =========================================================
elif st.session_state.phase == "post":
    top_back_button("during")

    st.subheader("Okuma Sonrası")

    metin = st.session_state.activity.get("sade_metin", "Metin yok.")

    st.markdown("<div class='card'><b>Metni 2–3 cümleyle anlat.</b></div>", unsafe_allow_html=True)

    voice_audio = st.audio_input("🎤 İstersen sesli anlat", key="summary_audio")
    if voice_audio is not None:
        st.audio(voice_audio)
        if st.button("🎙️ Yazıya Çevir", key="transcribe_summary_btn"):
            text = transcribe_audio_bytes(voice_audio.getvalue())
            if text:
                st.session_state.summary = text
                st.session_state.voice_text = text
                save_reading_process("VOICE_TO_TEXT", text, paragraf_no=None)
                st.success("Sesin yazıya çevrildi.")
            else:
                st.warning("Ses şu anda yazıya çevrilemedi.")

    if st.session_state.get("voice_text"):
        st.info(f"📝 {st.session_state.voice_text}")

    summ = st.text_area("Özetin", value=st.session_state.summary, height=120)
    st.session_state.summary = summ.strip()
    maybe_log_once("summary_auto", "POST_SUMMARY_AUTO", st.session_state.summary, paragraf_no=None)

    if st.session_state.summary and not st.session_state.get("summary_feedback_done", False):
        try:
            fb = generate_summary_feedback(metin, st.session_state.summary)
            st.session_state.summary_feedback = fb
            st.session_state.summary_feedback_done = True
            save_reading_process("AI_SUMMARY_FEEDBACK", fb, paragraf_no=None)
        except Exception:
            st.session_state.summary_feedback = ""

    if st.session_state.get("summary_feedback"):
        st.info(f"🤖 {st.session_state.summary_feedback}")

    st.divider()
    st.markdown("<div class='card'><b>Okurken zorlandın mı?</b></div>", unsafe_allow_html=True)
    difficulty = st.radio("Seç", ["Evet", "Hayır"], index=None, key="difficulty_radio_post")

    st.session_state.reflection_has_difficulty = difficulty or ""
    maybe_log_once("difficulty_auto", "POST_DIFFICULTY_AUTO", st.session_state.reflection_has_difficulty, paragraf_no=None)

    if difficulty == "Evet":
        st.markdown("<div class='card'><b>Zorlandığında ne yaptın?</b></div>", unsafe_allow_html=True)
        r1 = st.text_input("Kısa yaz", value=st.session_state.get("reflection_strategy", ""), key="reflection_strategy_input")
        st.session_state.reflection_strategy = (r1 or "").strip()
        maybe_log_once("reflection_strategy_auto", "POST_REFLECTION_STRATEGY_AUTO", st.session_state.reflection_strategy, paragraf_no=None)
    else:
        st.session_state.reflection_strategy = ""

    st.markdown("<div class='card'><b>Okurken sana en çok ne yardımcı oldu?</b></div>", unsafe_allow_html=True)
    r2 = st.text_input("Kısa yaz", value=st.session_state.get("reflection_next_time", ""), key="reflection_next_input")
    st.session_state.reflection_next_time = (r2 or "").strip()
    maybe_log_once("reflection_next_auto", "POST_REFLECTION_NEXT_AUTO", st.session_state.reflection_next_time, paragraf_no=None)

    st.divider()
    st.subheader("Öykü Haritası")

    templates = {
        "kahraman": "Bu öyküde ... vardı.",
        "mekan": "Olay ... yerinde geçti.",
        "zaman": "Olay ... zamanında oldu.",
        "problem": "Sorun şuydu: ...",
        "olaylar": "Önce ... oldu. Sonra ... oldu.",
        "cozum": "Sonunda ... oldu."
    }

    sm = st.session_state.story_map.copy()

    sm["kahraman"] = st.text_input("👤 Kahraman", value=sm["kahraman"], placeholder=templates["kahraman"], key="story_kahraman")
    sm["mekan"] = st.text_input("🏠 Mekân", value=sm["mekan"], placeholder=templates["mekan"], key="story_mekan")
    sm["zaman"] = st.text_input("🕒 Zaman", value=sm["zaman"], placeholder=templates["zaman"], key="story_zaman")
    sm["problem"] = st.text_input("⚠️ Problem", value=sm["problem"], placeholder=templates["problem"], key="story_problem")
    sm["olaylar"] = st.text_area("🔁 Olaylar", value=sm["olaylar"], height=100, placeholder=templates["olaylar"], key="story_olaylar")
    sm["cozum"] = st.text_input("✅ Çözüm", value=sm["cozum"], placeholder=templates["cozum"], key="story_cozum")

    st.session_state.story_map = sm

    maybe_log_once("story_kahraman_auto", "STORY_KAHRAMAN_AUTO", sm["kahraman"], paragraf_no=None)
    maybe_log_once("story_mekan_auto", "STORY_MEKAN_AUTO", sm["mekan"], paragraf_no=None)
    maybe_log_once("story_zaman_auto", "STORY_ZAMAN_AUTO", sm["zaman"], paragraf_no=None)
    maybe_log_once("story_problem_auto", "STORY_PROBLEM_AUTO", sm["problem"], paragraf_no=None)
    maybe_log_once("story_olaylar_auto", "STORY_OLAYLAR_AUTO", sm["olaylar"], paragraf_no=None)
    maybe_log_once("story_cozum_auto", "STORY_COZUM_AUTO", sm["cozum"], paragraf_no=None)

    if st.button("Öykü Haritasını Puanla"):
        filled = sum(1 for _, v in sm.items() if str(v).strip())
        st.session_state.story_map_filled = filled
        if filled < 3:
            st.warning("En az 3 alan doldur.")
        else:
            with st.spinner("AI puanlıyor..."):
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
                st.success(f"AI Puan: {total}/12")

    if st.session_state.get("storymap_feedback"):
        st.info(f"🤖 {st.session_state.storymap_feedback}")

    st.divider()
    if st.button("Sorulara Geç"):
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 5) QUESTIONS
# =========================================================
elif st.session_state.phase == "questions":

    st.subheader("Sorular")

    sorular = st.session_state.activity.get("sorular", [])
    total_q = len(sorular)

    if total_q == 0:
        st.error("Soru yok")
        st.stop()

    i = st.session_state.get("q_idx", 0)

    # 🔒 Index hatası fix
    if i >= total_q:
        i = total_q - 1
        st.session_state.q_idx = i

    q = sorular[i]

    st.write(f"Soru {i+1} / {total_q}")
    st.write(q["kok"])

    opts = ["A", "B", "C", "D"]

    key = f"q_{i}"
    prev = st.session_state.get(key)
    index = opts.index(prev) if prev in opts else None

    secim = st.radio(
        "Seç",
        opts,
        index=index,
        format_func=lambda x: f"{x}) {q.get(x,'')}",
        key=f"radio_{i}"
    )

    if secim:
        st.session_state[key] = secim

        if secim == q["dogru"]:
            st.success("Doğru")
        else:
            st.error("Yanlış")

    # 💡 İpucu
    if st.button("💡 İpucu"):
        try:
            hint = generate_ai_hint(metin, q, secim or "", level=1)
            st.session_state.ai_hint_text = hint
        except:
            st.session_state.ai_hint_text = "Metne tekrar bak."

    # 📄 Metni Göster
    if st.button("📄 Metni Göster"):
        st.write(st.session_state.activity.get("sade_metin", ""))

    # İpucu yazısı
    if st.session_state.get("ai_hint_text"):
        st.info(st.session_state.ai_hint_text)

    st.divider()

    # ⬅️ ➡️ Navigasyon
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️", disabled=(i == 0)):
            st.session_state.q_idx = max(0, i - 1)
            st.rerun()

    with col2:
        if st.button("➡️", disabled=(i >= total_q - 1)):
            st.session_state.q_idx = min(total_q - 1, i + 1)
            st.rerun()

    # Bitir
    if i == total_q - 1:
        if st.button("Bitir"):
            st.session_state.phase = "finalize"
            st.rerun()
# =========================================================
# 6) FINALIZE
# =========================================================
elif st.session_state.phase == "finalize":
    if not st.session_state.saved_perf:
        total_q = len(st.session_state.activity.get("sorular", []))
        qstat = st.session_state.get("question_status", {})
        dogru = sum(1 for v in qstat.values() if v == "correct")
        yanlis = sum(1 for v in qstat.values() if v == "wrong")
        gecilen = sum(1 for v in qstat.values() if v == "skipped")
        sure = round((time.time() - st.session_state.start_t) / 60, 2)
        basari_yuzde = f"%{round((dogru / total_q) * 100, 1)}" if total_q else "%0"

        hatali = []
        for idx, v in qstat.items():
            if v in {"wrong", "skipped"}:
                hatali.append(f"{idx+1}:{v}")
        hatali_text = ", ".join(hatali) if hatali else "Hepsi doğru"

        row = [
            st.session_state.session_id,
            st.session_state.user,
            st.session_state.login_time,
            sure,
            "",
            basari_yuzde,
            total_q,
            dogru,
            hatali_text,
            st.session_state.metin_id,
            st.session_state.hints,
            "Evet",
            "Evet",
            0,
            0,
            st.session_state.get("prediction", ""),
            "",
            st.session_state.get("reading_speed", ""),
            st.session_state.get("repeat_count", 0),
            st.session_state.get("tts_count", 0),
            st.session_state.get("reread_count", 0),
            1 if (st.session_state.get("final_important_note", "") or "").strip() else 0,
            1 if (st.session_state.get("prior_knowledge", "") or "").strip() else 0,
        ]

        ok = append_row_safe("Performans", row)
        if ok:
            st.session_state.last_report = {
                "basari_yuzde": basari_yuzde,
                "dogru": dogru,
                "yanlis": yanlis,
                "gecilen": gecilen,
                "total_q": total_q,
                "sure_dk": sure,
                "hints": int(st.session_state.get("hints", 0)),
                "prediction": (st.session_state.get("prediction", "") or "").strip(),
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
    top_back_button("questions")

    st.success("✅ Çalışma tamamlandı ve kaydedildi.")

    rep = st.session_state.get("last_report", {}) or {}
    story_total = st.session_state.get("story_map_last_total")
    story_reason = st.session_state.get("story_map_last_reason", "")

    if rep:
        st.subheader("Sonuçlar")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='card'><b>Başarı</b><br/>{rep.get('basari_yuzde','')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>Doğru</b><br/>{rep.get('dogru',0)}/{rep.get('total_q',0)}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card'><b>Yanlış</b><br/>{rep.get('yanlis',0)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>Geçilen</b><br/>{rep.get('gecilen',0)}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='card'><b>Süre</b><br/>{rep.get('sure_dk',0)} dk</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'><b>İpucu</b><br/>{rep.get('hints',0)}</div>", unsafe_allow_html=True)

        if rep.get("important_note"):
            st.markdown(f"<div class='card'><b>Metindeki En Önemli Şey</b><br/>{rep.get('important_note')}</div>", unsafe_allow_html=True)
        if rep.get("prior_knowledge"):
            st.markdown(f"<div class='card'><b>Ön Bilgi</b><br/>{rep.get('prior_knowledge')}</div>", unsafe_allow_html=True)
        if rep.get("summary"):
            st.markdown(f"<div class='card'><b>Özet</b><br/>{rep.get('summary')}</div>", unsafe_allow_html=True)

        st.subheader("Grafik")
        df = pd.DataFrame(
            {
                "Değer": [
                    float(rep.get("sure_dk", 0)),
                    int(rep.get("dogru", 0)),
                    int(rep.get("yanlis", 0)),
                    int(rep.get("gecilen", 0)),
                    int(rep.get("hints", 0)),
                    int(rep.get("tts_count", 0)),
                    int(rep.get("reread_count", 0)),
                ]
            },
            index=[
                "Süre (dk)",
                "Doğru",
                "Yanlış",
                "Geçilen",
                "İpucu",
                "Dinleme",
                "Tekrar Okuma",
            ],
        )
        st.bar_chart(df)

        png_bytes = build_report_chart_bytes(rep)
        report_text = build_report_text(rep, story_total, story_reason)
        report_json = json.dumps(
            {
                "report": rep,
                "story_map_total": story_total,
                "story_map_reason": story_reason,
                "story_map": st.session_state.get("story_map", {}),
            },
            ensure_ascii=False,
            indent=2
        )

        d1, d2, d3 = st.columns(3)
        with d1:
            if png_bytes:
                st.download_button("Grafiği İndir (PNG)", data=png_bytes, file_name="okuma_grafigi.png", mime="image/png")
        with d2:
            st.download_button("Skor Raporu İndir (TXT)", data=report_text.encode("utf-8"), file_name="okuma_raporu.txt", mime="text/plain")
        with d3:
            st.download_button("Tüm Sonuçları İndir (JSON)", data=report_json.encode("utf-8"), file_name="okuma_sonuclari.json", mime="application/json")

    if story_total is not None:
        st.markdown(f"<div class='card'><b>Öykü Haritası Puanı</b><br/>{story_total}/12</div>", unsafe_allow_html=True)
        if story_reason:
            st.markdown(f"<div class='small-note'>{story_reason}</div>", unsafe_allow_html=True)

    if st.session_state.get("summary_feedback"):
        st.markdown(f"<div class='card'><b>Özet Geri Bildirimi</b><br/>{st.session_state.get('summary_feedback')}</div>", unsafe_allow_html=True)
    if st.session_state.get("storymap_feedback"):
        st.markdown(f"<div class='card'><b>Öykü Haritası Yorumu</b><br/>{st.session_state.get('storymap_feedback')}</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yeni Metin"):
            st.session_state.phase = "auth"
            st.session_state.metin_id = ""
            reset_activity_states()
            st.rerun()
    with c2:
        if st.button("Çıkış Yap"):
            st.session_state.clear()
            st.rerun() 
