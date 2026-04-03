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
# OKUMA DOSTUM — ÖÖG UYUMLU TAM SÜRÜM (GÜNCELLENMİŞ)
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

  .card {
    background: #ffffff;
    padding: 16px;
    border-radius: 16px;
    border: 1px solid #e7eef7;
    margin-bottom: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
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
    return int(m.group(1)) if m else 0

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
        return None

def split_paragraphs(text: str):
    text = (text or "").replace("\r", "\n").strip()
    if not text: return []
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(raw_paras) <= 1:
        flat = re.sub(r"\s+", " ", text).strip()
        return [flat] if len(flat) < 900 else [flat[:len(flat)//2], flat[len(flat)//2:]]
    return raw_paras

# =========================================================
# OPENAI
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_json_request(system_prompt, user_text, model="gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        response_format={"type": "json_object"},
        temperature=0,
    )

def openai_text_request(system_prompt, user_text, model="gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        temperature=0.3,
    )

def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes: return ""
    try:
        bio = BytesIO(audio_bytes)
        bio.name = "speech.wav"
        resp = client.audio.transcriptions.create(model="whisper-1", file=bio)
        return (getattr(resp, "text", "") or "").strip()
    except: return ""

# =========================================================
# FEEDBACKS
# =========================================================
def generate_ai_hint(metin, soru, wrong_choice, level=1):
    instruction = ["Kısa ipucu ver.", "Biraz daha açık ipucu ver.", "En açık ipucunu ver."][min(level-1, 2)]
    sys = f"Sen sabırlı bir okuma öğretmenisin. Cevabı doğrudan söyleme. {instruction}"
    payload = {"metin": metin[:2000], "soru": soru.get("kok"), "dogru": soru.get("dogru"), "ogrenci": wrong_choice}
    resp = openai_text_request(sys, json.dumps(payload, ensure_ascii=False))
    return resp.choices[0].message.content.strip()

def generate_summary_feedback(metin, ozet):
    sys = "Öğrenci özetini değerlendir. Nazik ol, 1 öneri ver."
    resp = openai_text_request(sys, f"Metin: {metin[:2000]}\nÖzet: {ozet}")
    return resp.choices[0].message.content.strip()

def explain_word_simple(word, metin):
    sys = "Kelimeyi ortaokul seviyesinde basitçe açıkla."
    resp = openai_text_request(sys, f"Kelime: {word}\nMetin: {metin[:1000]}")
    return resp.choices[0].message.content.strip()

# =========================================================
# GOOGLE SHEETS
# =========================================================
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    if "\\n" in info.get("private_key", ""):
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    return get_gs_client().open_by_url(st.secrets["GSHEET_URL"])

def get_ws(sheet_name):
    sh = get_spreadsheet()
    for w in sh.worksheets():
        if w.title.strip().lower() == sheet_name.strip().lower(): return w
    return None

def read_sheet_records(sheet_name):
    ws = get_ws(sheet_name)
    return ws.get_all_records() if ws else []

def append_row_safe(sheet_name, row):
    try:
        ws = get_ws(sheet_name)
        if ws: ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except: return False

def save_reading_process(kayit_turu, icerik, paragraf_no=None):
    row = [st.session_state.get("session_id", ""), st.session_state.get("user", ""), now_tr(), "", st.session_state.get("metin_id", ""), paragraf_no or "", kayit_turu, (icerik or "")[:40000]]
    append_row_safe("OkumaSüreci", row)

# =========================================================
# RUBRIK & BANKA
# =========================================================
def compute_metacog_signals():
    qa = st.session_state.get("question_attempts", {})
    attempts_total = sum(int(v) for v in qa.values())
    return {
        "prediction_len": len((st.session_state.get("prediction") or "").strip()),
        "repeat_count": int(st.session_state.get("repeat_count", 0)),
        "hints": int(st.session_state.get("hints", 0)),
        "attempts_total": attempts_total,
        "summary_len": len((st.session_state.get("summary") or "").strip()),
        "story_map_total": int(st.session_state.get("story_map_last_total") or 0)
    }

def rule_based_metacog_score(sig):
    p, m, e = 1 if sig["prediction_len"] > 5 else 0, min(sig["attempts_total"], 3), min(sig["summary_len"]//20, 3)
    return {"planlama": p, "izleme": m, "degerlendirme": e, "total": p+m+e}

def list_metin_ids():
    rows = read_sheet_records("MetinBankasi")
    return sorted(list(set([_norm(r.get("metin_id")) for r in rows if _norm(r.get("metin_id"))])))

def load_activity_from_bank(metin_id):
    mrows = read_sheet_records("MetinBankasi")
    match_m = [r for r in mrows if _norm(r.get("metin_id", r.get("METIN_ID"))) == metin_id]
    if not match_m: return None, "Metin bulunamadı."
    
    metin = match_m[0].get("metin", match_m[0].get("METIN", ""))
    qrows = read_sheet_records("SoruBankasi")
    match_q = [r for r in qrows if _norm(r.get("metin_id", r.get("METIN_ID"))) == metin_id]
    
    sorular = []
    opts = option_letters_for_metin(metin_id)
    for r in match_q:
        q_obj = {"kok": r.get("kok", r.get("KOK")), "dogru": str(r.get("dogru", r.get("DOGRU"))).upper()}
        for L in opts: q_obj[L] = r.get(L) or r.get(L.lower())
        sorular.append(q_obj)
    
    return {"sade_metin": metin, "baslik": match_m[0].get("baslik"), "sorular": sorular, "opts": opts}, ""

# =========================================================
# STORY MAP AI (ESNEK PUANLAMA EKLENDİ)
# =========================================================
def ai_score_story_map(metin, sm):
    sys = """Sen ÖÖG uzmanı bir öğretmensin. Öğrencinin öykü haritasını metne göre puanla.
    KRİTİK KURAL: Eş anlamlı, yakın anlamlı kelimeleri (örn: ev-yuva, okul-mektep) veya doğru betimlemeleri TAM PUAN (2) kabul et. 
    JSON formatında döndür: {"scores": {"kahraman": 2, "mekan": 2, "zaman": 2, "problem": 2, "olaylar": 2, "cozum": 2}, "reason": "Kısa özet"}"""
    user_payload = f"Metin: {metin[:3000]}\nCevaplar: {json.dumps(sm, ensure_ascii=False)}"
    try:
        resp = openai_json_request(sys, user_payload)
        data = json.loads(resp.choices[0].message.content)
        return data["scores"], sum(data["scores"].values()), data.get("reason", "")
    except: return {k:0 for k in sm.keys()}, 0, "Hata oluştu."

# =========================================================
# STATE & PHASE MANAGEMENT
# =========================================================
def reset_activity_states():
    st.session_state.q_idx = 0
    st.session_state.question_attempts = {}
    st.session_state.question_status = {}
    st.session_state.story_map = {"kahraman":"", "mekan":"", "zaman":"", "problem":"", "olaylar":"", "cozum":""}
    st.session_state.p_idx = 0
    st.session_state.start_t = time.time()
    st.session_state.saved_perf = False
    st.session_state.hints = 0
    st.session_state.repeat_count = 0
    st.session_state.prediction = ""
    st.session_state.reading_speed = ""
    st.session_state.summary = ""

if "phase" not in st.session_state: st.session_state.phase = "auth"

if st.session_state.phase != "auth":
    if st.button("Çıkış", key="exit_btn"):
        st.session_state.clear()
        st.rerun()

# 1) AUTH
if st.session_state.phase == "auth":
    st.markdown("<div class='emoji-row'>📚 ✨ 🧠 🌈 📖</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-box'><div class='hero-title'>Okuma Dostum</div></div>", unsafe_allow_html=True)
    u = st.text_input("Öğrenci Kodun")
    metin_listesi = list_metin_ids()
    selected_id = st.selectbox("Metin seç", metin_listesi)
    if st.button("Başlayalım"):
        if u and selected_id:
            st.session_state.user, st.session_state.metin_id = u, selected_id
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.login_time = now_tr()
            act, err = load_activity_from_bank(selected_id)
            if act:
                st.session_state.activity = act
                st.session_state.paragraphs = split_paragraphs(act["sade_metin"])
                reset_activity_states()
                save_reading_process("SESSION_START", f"Metin: {selected_id}")
                go_to_phase("pre")
            else: st.error(err)

# 2) PRE
elif st.session_state.phase == "pre":
    st.subheader("Okuma Öncesi")
    st.write(f"Başlık: {st.session_state.activity.get('baslik')}")
    st.session_state.prediction = st.text_input("Sence bu metin ne hakkında?", value=st.session_state.prediction)
    st.session_state.reading_speed = st.radio("Okuma hızın?", ["Yavaş", "Orta", "Hızlı"], index=None)
    if st.button("Metne Geç"):
        if st.session_state.reading_speed: go_to_phase("during")
        else: st.warning("Hız seç!")

# 3) DURING
elif st.session_state.phase == "during":
    p_idx = st.session_state.p_idx
    paras = st.session_state.paragraphs
    st.subheader(f"Bölüm {p_idx+1} / {len(paras)}")
    st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)
    
    if st.button("🔊 Dinle"):
        st.session_state.repeat_count += 1
        fp = get_audio(paras[p_idx])
        if fp: st.audio(fp)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Geri", disabled=(p_idx==0)):
            st.session_state.p_idx -= 1
            st.rerun()
    with c2:
        if p_idx < len(paras)-1:
            if st.button("İleri ➡️"):
                st.session_state.p_idx += 1
                st.rerun()
        else:
            if st.button("Bitir"): go_to_phase("post")

# 4) POST (STORY MAP)
elif st.session_state.phase == "post":
    st.subheader("Öykü Haritası")
    sm = st.session_state.story_map
    sm["kahraman"] = st.text_input("👤 Kahraman", value=sm["kahraman"])
    sm["mekan"] = st.text_input("🏠 Mekan", value=sm["mekan"])
    sm["problem"] = st.text_input("⚠️ Problem", value=sm["problem"])
    sm["olaylar"] = st.text_area("🔁 Olaylar", value=sm["olaylar"])
    sm["cozum"] = st.text_input("✅ Çözüm", value=sm["cozum"])
    
    if st.button("Puanla ve Devam Et"):
        with st.spinner("AI Puanlıyor..."):
            scores, total, reason = ai_score_story_map(st.session_state.activity["sade_metin"], sm)
            st.session_state.story_map_last_total = total
            st.session_state.story_map_last_reason = reason
            st.success(f"Puan: {total}/12")
            time.sleep(1.5)
            go_to_phase("questions")

# 5) QUESTIONS (DÜZELTİLDİ)
elif st.session_state.phase == "questions":
    sorular = st.session_state.activity["sorular"]
    i = st.session_state.q_idx
    q = sorular[i]
    st.subheader(f"Soru {i+1} / {len(sorular)}")
    st.markdown(f"<div class='card'>{q['kok']}</div>", unsafe_allow_html=True)
    
    # RADYO SIFIRLAMA İÇİN DİNAMİK KEY
    r_key = f"radio_q_{i}_at_{st.session_state.question_attempts.get(i, 0)}"
    secim = st.radio("Seçimin:", st.session_state.activity["opts"], index=None, key=r_key, format_func=lambda x: f"{x}: {q.get(x)}")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Kontrol Et"):
            st.session_state.question_attempts[i] = st.session_state.question_attempts.get(i, 0) + 1
            if secim == q["dogru"]:
                st.session_state.question_status[i] = "correct"
                if i < len(sorular)-1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else: go_to_phase("finalize")
            else:
                st.error("Yanlış, tekrar dene!")
                st.rerun()
    with c2:
        if st.button("Soruyu Geç"):
            st.session_state.question_status[i] = "skipped"
            if i < len(sorular)-1:
                st.session_state.q_idx += 1
                st.rerun()
            else: go_to_phase("finalize")

# 6) FINALIZE
elif st.session_state.phase == "finalize":
    st.balloons()
    st.header("Tebrikler! 🎉")
    dogru = sum(1 for v in st.session_state.question_status.values() if v == "correct")
    st.write(f"Skor: {dogru} / {len(st.session_state.activity['sorular'])}")
    if st.button("Başa Dön"):
        st.session_state.clear()
        st.rerun()
