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

# =========================================================
# OKUMA DOSTUM — BANKA + SÜREÇ LOG (SINIF KALDIRILDI)
#
# MetinBankasi: metin_id | metin | baslik | pre_ipucu | (sinif olabilir ama kullanılmıyor)
# SoruBankasi : metin_id | soru_no | kok | A | B | C | (D) | dogru | (sinif olabilir ama kullanılmıyor)
#
# SORU SAYISI:
# - Metin_001..Metin_007: 6 soru
# - Metin_008 ve sonrası: 7 soru
#
# ŞIK SAYISI:
# - Metin_001..Metin_004: ABC
# - Metin_005 ve sonrası: ABCD
#
# OKUMA EKRANI:
# - Cümle ortasında kesmez
# - Kısa parçaları birleştirir
# - Hedef blok: 900-1400 karakter
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
  html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 20px; }
  .stButton button {
    width: 100%; border-radius: 18px; height: 3.0em;
    font-weight: 600; font-size: 20px !important;
    border: 2px solid #eee; background-color: #3498db; color: white;
  }
  .highlight-box {
    background-color: #ffffff; padding: 26px; border-radius: 22px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.08);
    border-left: 12px solid #f1c40f; font-size: 22px !important;
    line-height: 1.9 !important; margin-bottom: 18px;
    white-space: pre-wrap;
  }
  .small-note { color:#666; font-size:16px; }
  .card { background:#fff; padding:16px; border-radius:18px; border:1px solid #eee; margin-bottom:10px; }
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
# METİN BÖLME (OKUMA EKRANI İÇİN)
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

def split_paragraphs(text: str, target_min=900, target_max=1400, tail_min=350):
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
                        max_len=max(250, target_max - len(block) - 1)
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
            if len(buf) < target_min and (len(buf) + 1 + len(b)) <= (target_max + 700):
                buf = (buf + " " + b).strip()
            else:
                final.append(buf)
                buf = b
    if buf:
        final.append(buf)

    if len(final) >= 2 and len(final[-1]) < tail_min:
        if len(final[-2]) + 1 + len(final[-1]) <= (target_max + 900):
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
                temperature=temperature,  # ✅ daha stabil (sallamayı azaltır)
            )
        except (RateLimitError, APIError, APITimeoutError):
            wait = min(2 ** attempt, 20) + random.uniform(0, 1.0)
            st.warning(f"⚠️ Yoğunluk var, tekrar deneniyor... ({attempt+1}/{max_retries})")
            time.sleep(wait)
    st.error("❌ OpenAI yoğunluğu çok fazla. Biraz sonra tekrar deneyin.")
    st.stop()

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
        "",  # sinif kaldırıldı -> boş
        st.session_state.get("metin_id", ""),
        paragraf_no if paragraf_no is not None else "",
        kayit_turu,
        (icerik or "")[:45000],
    ]
    append_row_safe("OkumaSüreci", row)

# =========================================================
# ÜSTBİLİŞSEL RUBRİK (KURAL TABANLI)
# Google Sheet’te SEKME ADI: UstBilisselRubrik
# Kolonlar:
# session_id | user | time | metin_id | planlama | izleme | degerlendirme | transfer | total | reason | signals_json
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
    # PLANLAMA 0-2
    plan = 0
    if sig["prediction_len"] >= 5:
        plan += 1
    if sig["attention_ok"]:
        plan += 1
    plan = min(plan, 2)

    # İZLEME 0-3
    monitor = 0
    if (sig["reread_count"] + sig["tts_count"]) >= 1:
        monitor += 1
    if sig["hints"] >= 1:
        monitor += 1
    if sig["attempts_total"] >= 2:
        monitor += 1
    monitor = min(monitor, 3)

    # DEĞERLENDİRME 0-3
    evals = 0
    if sig["summary_len"] >= 20:
        evals += 1
    if sig["important_note_len"] >= 10:
        evals += 1
    if sig["story_map_total"] >= 6 or sig["story_map_filled"] >= 4:
        evals += 1
    evals = min(evals, 3)

    # TRANSFER 0-2
    transfer = 0
    if sig["reflection_next_len"] >= 8:
        transfer = 1
    if sig["reflection_next_len"] >= 20:
        transfer = 2

    total = plan + monitor + evals + transfer
    reason = "Kural tabanlı: planlama(tahmin+dikkat), izleme(tekrar/tts/ipucu/deneme), değerlendirme(özet/önemli bilgi/story map), transfer(gelecek planı)."
    return {
        "planlama": plan,
        "izleme": monitor,
        "degerlendirme": evals,
        "transfer": transfer,
        "total": total,
        "reason": reason,
    }

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
# BANKA OKUMA (SINIF FİLTRESİ YOK)
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
# STORY MAP AI (KANIT ŞARTI: "SALLAMA" YOK)
# =========================================================
def ai_score_story_map(metin: str, sm: dict):
    metin_short = (metin or "")[:4500]
    sm_safe = {k: (v or "")[:600] for k, v in (sm or {}).items()}

    rubrik = """
Rubrik (0-2):
0 = boş / alakasız / metinle uyuşmuyor
1 = kısmen doğru ama eksik / belirsiz
2 = doğru ve metinle uyumlu (kısa da olsa doğru bilgi)

ÇOK ÖNEMLİ KURAL:
- Her alan için evidence metinden AYNEN kopyalanmış 3-12 kelimelik bir ifade olmalı.
- Evidence metinde birebir geçmiyorsa: o alanın puanı 0 olmalı.
- Evidence üretemiyorsan puan veremezsin.
"""

    schema = """
Sadece JSON üret:
{
  "scores": {"kahraman":0|1|2,"mekan":0|1|2,"zaman":0|1|2,"problem":0|1|2,"olaylar":0|1|2,"cozum":0|1|2},
  "evidence": {"kahraman":"...","mekan":"...","zaman":"...","problem":"...","olaylar":"...","cozum":"..."},
  "total": 0-12,
  "reason": "1-2 cümle Türkçe kısa gerekçe"
}
Kural: evidence metinde AYNEN geçmiyorsa ilgili score = 0 olmalı.
total = scores toplamı olmalı.
"""

    sys = f"""
Sen özel eğitim/ÖÖG alanında deneyimli bir öğretmensin.
İlköğretim düzeyine göre (5-6. sınıf bandı) değerlendir.
{rubrik}
{schema}
"""

    user = json.dumps({"metin": metin_short, "story_map": sm_safe}, ensure_ascii=False)
    resp = openai_json_request(sys, user, model="gpt-4o-mini", temperature=0)

    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
    except Exception:
        data = {"scores": {}, "evidence": {}, "total": 0, "reason": "AI çıktısı okunamadı."}

    scores = data.get("scores", {}) or {}
    evidence = data.get("evidence", {}) or {}

    def clamp02(x):
        try:
            x = int(x)
        except Exception:
            x = 0
        return 0 if x < 0 else 2 if x > 2 else x

    metin_l = metin_short.lower()

    def evidence_ok(ev: str) -> bool:
        ev = (ev or "").strip()
        if not ev:
            return False
        if len(ev) < 8 or len(ev) > 120:
            return False
        return ev.lower() in metin_l  # ✅ birebir kontrol

    out = {}
    forced_zero = []
    for key in ["kahraman", "mekan", "zaman", "problem", "olaylar", "cozum"]:
        s = clamp02(scores.get(key, 0))
        ev = evidence.get(key, "")
        if not evidence_ok(ev):
            if s != 0:
                forced_zero.append(key)
            s = 0
        out[key] = s

    total = sum(out.values())
    reason = (data.get("reason") or "").strip()[:200]
    if forced_zero:
        reason = (reason + f" | Kanıt metinde yok: {', '.join(forced_zero)} → 0")[:200]

    return out, total, reason

def save_story_map_row(sm: dict, scores: dict, total: int, reason: str):
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        "",  # sinif kaldırıldı -> boş
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
    st.session_state.correct_no_hint = 0
    st.session_state.correct_with_hint = 0
    st.session_state.question_attempts = {}
    st.session_state.show_text_in_questions = False

    # ✅ ÜSTBİLİŞSEL YANSITMA
    st.session_state.reflection_strategy = ""
    st.session_state.reflection_next_time = ""

    # ✅ DONE ekranında göstermek için
    st.session_state.metacog_last_total = None

if "phase" not in st.session_state:
    st.session_state.phase = "auth"
if "busy" not in st.session_state:
    st.session_state.busy = False

# Global çıkış
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

        st.session_state.paragraphs = split_paragraphs(activity.get("sade_metin", ""))
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
        save_reading_process("PRE_ATTENTION", "Evet" if attention else "Hayır", paragraf_no=None)
        save_reading_process("PRE_SPEED", speed, paragraf_no=None)

        st.session_state.phase = "during"
        st.rerun()

# =========================================================
# 4) DURING
# =========================================================
elif st.session_state.phase == "during":
    st.subheader("🟩 Okuma Sırası (DURING-READING)")

    metin = st.session_state.activity.get("sade_metin", "Metin yok.")

    metin_hash = hash(metin)
    if st.session_state.get("metin_hash") != metin_hash:
        st.session_state.paragraphs = split_paragraphs(metin, target_min=900, target_max=1400)
        st.session_state.metin_hash = metin_hash

    paras = st.session_state.get("paragraphs", []) or []
    p_idx = st.session_state.get("p_idx", 0)

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

        with c2:
            st.markdown(
                f"<div class='small-note'>Seçtiğin hız: <b>{st.session_state.reading_speed}</b> | "
                f"Tekrar (dinleme+tekrar okuma): <b>{st.session_state.repeat_count}</b> | "
                f"Bölüm: <b>{min(p_idx+1, len(paras))}/{len(paras)}</b></div>",
                unsafe_allow_html=True
            )

        st.divider()
        st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)

        coln1, coln2 = st.columns(2)
        with coln1:
            if st.button("🔁 Bu bölümü tekrar oku", key=f"repeat_p_{p_idx}"):
                st.session_state.repeat_count += 1
                st.session_state.reread_count += 1
                save_reading_process("REPEAT_READ", "Bölüm tekrar okundu", paragraf_no=p_idx + 1)
                st.info("Tekrar okudun. Hazır olunca devam edebilirsin.")
        with coln2:
            if st.button("➡️ Sonraki bölüm", key=f"next_p_{p_idx}"):
                st.session_state.p_idx = p_idx + 1
                st.rerun()
    else:
        st.markdown("<div class='card'><b>Metnin En Önemli Şeyi</b><br/>Sence bu metindeki en önemli şey neydi? (1 cümle)</div>", unsafe_allow_html=True)
        st.session_state.final_important_note = st.text_input("En önemli şey:", value=st.session_state.final_important_note)

        if st.button("📌 Kaydet (1 kez)"):
            if st.session_state.final_important_note.strip():
                if not st.session_state.final_important_saved:
                    st.session_state.final_important_saved = True
                    save_reading_process("IMPORTANT_NOTE_FINAL", st.session_state.final_important_note.strip(), paragraf_no=None)
                    st.success("Kaydedildi!")
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
    metin = st.session_state.activity.get("sade_metin", "Metin yok.")

    st.markdown("<div class='card'><b>Özetleme</b><br/>Metni 2–3 cümleyle anlat.</div>", unsafe_allow_html=True)
    summ = st.text_area("Özetin:", value=st.session_state.summary, height=120)

    if st.button("Özeti Kaydet ✅"):
        st.session_state.summary = summ.strip()
        if st.session_state.summary:
            save_reading_process("POST_SUMMARY", st.session_state.summary, paragraf_no=None)
        st.success("✅ Özet kaydedildi!")

    # ✅ ÜSTBİLİŞSEL YANSITMA
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

    st.divider()
    st.subheader("🗺️ Öykü Haritası (Story Map)")
    st.markdown("""
    <div class='card'><b>Nasıl dolduracaksın?</b><br/>
    Metindeki öykünün parçalarını tek tek yaz. Kısa yazman yeterli (1–2 cümle).</div>
    """, unsafe_allow_html=True)

    sm = st.session_state.story_map
    col1, col2 = st.columns(2)
    with col1:
        sm["kahraman"] = st.text_input("👤 Kahraman(lar)", value=sm["kahraman"])
        sm["mekan"] = st.text_input("🏠 Mekân", value=sm["mekan"])
        sm["zaman"] = st.text_input("🕒 Zaman", value=sm["zaman"])
    with col2:
        sm["problem"] = st.text_input("⚠️ Problem (Sorun)", value=sm["problem"])
        sm["olaylar"] = st.text_area("🔁 Olaylar (Kısaca sırayla)", value=sm["olaylar"], height=90)
        sm["cozum"] = st.text_input("✅ Çözüm / Sonuç", value=sm["cozum"])

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
                    st.success(f"✅ Kaydedildi! AI Puan: {total}/12")
                    st.caption(f"Gerekçe: {reason}")

    with col_b:
        st.markdown(
            "<div class='small-note'>AI Puan: ✅</div>" if st.session_state.story_map_ai_scored
            else "<div class='small-note'>AI Puan: ⏳</div>",
            unsafe_allow_html=True
        )

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
        st.subheader(f"Soru {i+1} / {total_q}")
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
                    st.session_state.q_idx = i + 1
                    st.rerun()
                else:
                    st.error("Tekrar dene!")

        if st.button("💡 İpucu Al", key=f"hint_{i}"):
            st.session_state.hints += 1
            st.session_state.show_text_in_questions = True
            save_reading_process("HINT", f"Soru {i+1} | ipucu_alindi", paragraf_no=None)
            st.info("📌 Metni '📄 Metin' bölümünde açtım. Anahtar kelimeleri metinde ara ve ilgili bölümü tekrar oku.")

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
                "",  # sinif kaldırıldı -> boş
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
                # ✅ ÜSTBİLİŞSEL RUBRİK KAYDI
                try:
                    sig = compute_metacog_signals()
                    scores = rule_based_metacog_score(sig)
                    save_metacog_rubric_row(scores, scores.get("reason", ""), sig)
                    st.session_state.metacog_last_total = scores.get("total", 0)  # ✅ DONE ekranı için
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

    sm_total = st.session_state.get("story_map_last_total")
    sm_reason = st.session_state.get("story_map_last_reason", "")
    mc_total = st.session_state.get("metacog_last_total")

    if sm_total is not None:
        st.info(f"🗺️ Öykü Haritası (AI) Puanın: {sm_total}/12")
        if sm_reason:
            st.caption(f"Gerekçe: {sm_reason}")

    if mc_total is not None:
        st.info(f"🧠 Üstbilişsel Rubrik Puanın: {mc_total}/10")

    if st.button("Yeni Metin"):
        st.session_state.phase = "auth"
        st.session_state.metin_id = ""
        reset_activity_states()
        st.rerun()
    if st.button("Çıkış"):
        st.session_state.clear()
        st.rerun()
