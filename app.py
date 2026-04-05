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
    text = (text or "").replace("\r", "\n").strip()
    if not text:
        return []

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()

    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    if len(raw_paras) <= 1:
        flat = re.sub(r"\s+", " ", text).strip()
        L = len(flat)

        if L < 900:
            return [flat]
        elif L < 1800:
            return _split_single_block_to_n_parts(flat, 2)
        else:
            return _split_single_block_to_n_parts(flat, 3)

    total_len = sum(len(p) for p in raw_paras)

    if total_len < 900:
        target_blocks = 1
    elif total_len < 1800:
        target_blocks = 2
    else:
        target_blocks = 3

    target_size = total_len / target_blocks
    blocks = []
    current = ""

    for para in raw_paras:
        para = para.strip()
        if not para:
            continue

        if not current:
            current = para
            continue

        if len(current) + len(para) + 2 <= target_size * 1.20:
            current += "\n\n" + para
        else:
            blocks.append(current.strip())
            current = para

    if current.strip():
        blocks.append(current.strip())

    while len(blocks) > 3:
        blocks[-2] = blocks[-2].strip() + "\n\n" + blocks[-1].strip()
        blocks.pop()

    while len(blocks) < 3:
        longest_i = max(range(len(blocks)), key=lambda i: len(blocks[i]))
        longest = blocks[longest_i]

        if len(longest) < 1000:
            break

        split_parts = _split_single_block_to_n_parts(longest, 2)
        if len(split_parts) != 2:
            break

        blocks = blocks[:longest_i] + split_parts + blocks[longest_i+1:]

        if len(blocks) >= 3:
            break

    return [b.strip() for b in blocks if b.strip()]

def build_report_chart_bytes(rep: dict):
    try:
        import matplotlib.pyplot as plt
        labels = ["Süre", "Doğru", "Yanlış", "Geçilen", "İpucu", "Dinleme", "Tekrar"]
        values = [
            float(rep.get("sure_dk", 0)),
            int(rep.get("dogru", 0)),
            int(rep.get("yanlis", 0)),
            int(rep.get("gecilen", 0)),
            int(rep.get("hints", 0)),
            int(rep.get("tts_count", 0)),
            int(rep.get("reread_count", 0)),
        ]
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.bar(labels, values)
        ax.set_title("Bugünkü Okuma Özeti")
        fig.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

def build_report_text(rep: dict, story_total, story_reason):
    lines = [
        "OKUMA DOSTUM RAPORU",
        f"Tarih: {now_tr()}",
        f"Öğrenci: {st.session_state.get('user','')}",
        f"Metin ID: {st.session_state.get('metin_id','')}",
        "",
        f"Başarı: {rep.get('basari_yuzde','')}",
        f"Doğru: {rep.get('dogru',0)} / {rep.get('total_q',0)}",
        f"Yanlış: {rep.get('yanlis',0)}",
        f"Geçilen: {rep.get('gecilen',0)}",
        f"Süre (dk): {rep.get('sure_dk',0)}",
        f"İpucu: {rep.get('hints',0)}",
        f"Dinleme: {rep.get('tts_count',0)}",
        f"Tekrar Okuma: {rep.get('reread_count',0)}",
        "",
        f"Tahmin: {rep.get('prediction','')}",
        f"Okuma Hızı: {rep.get('speed','')}",
        f"En Önemli Şey: {rep.get('important_note','')}",
        f"Ön Bilgi: {rep.get('prior_knowledge','')}",
        f"Özet: {rep.get('summary','')}",
        "",
        f"Öykü Haritası Puanı: {story_total if story_total is not None else ''}",
        f"Öykü Haritası Gerekçe: {story_reason or ''}",
    ]
    return "\n".join(lines)

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
def compute
