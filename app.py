import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
from io import BytesIO
import tempfile
import re
import json
import uuid
import time

# =========================================================
# OKUMA DOSTUM — MEB + ÖÖG + Sunuş Yoluyla Öğretim
# FIX:
# - draft set hatası yok (form clear_on_submit)
# - metin yapıştır: Kaydet butonu (Ctrl+Enter gereksiz)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 20px !important; }
p, li, div, span { line-height: 1.9 !important; }
.stChatMessage p { font-size: 20px !important; line-height: 1.9 !important; }
.stTextInput input, .stTextArea textarea {
  font-size: 20px !important; line-height: 1.9 !important; padding: 14px 14px !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { font-size: 18px !important; opacity: .65; }
.stButton button{ font-size: 18px !important; border-radius: 16px !important; padding: 10px 14px !important; }
.stMarkdown { word-spacing: 0.16em !important; letter-spacing: 0.02em !important; }
.block-container { padding-top: 2rem; padding-bottom: 2.0rem; max-width: none; }
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:18px; padding:16px 18px; margin:12px 0;
  background: rgba(255,255,255,.92);
}
.badge{
  display:inline-block; padding:6px 12px; border-radius:999px;
  border:1px solid rgba(0,0,0,.12); font-size:16px; opacity:.85; margin-bottom:10px;
}
.smallhint{ font-size: 14px; opacity: .7; }
</style>
""",
    unsafe_allow_html=True,
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ Sheets ------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
gc = gspread.authorize(credentials)
workbook = gc.open_by_url(st.secrets["GSHEET_URL"])

try:
    chat_sheet = workbook.worksheet("Sohbet")
except WorksheetNotFound:
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=5000, cols=25)

try:
    perf_sheet = workbook.worksheet("Performans")
except WorksheetNotFound:
    perf_sheet = workbook.add_worksheet(title="Performans", rows=5000, cols=25)

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

def sheet_append_safe(sheet, row):
    try:
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Sheet yazma hatası: {e}")

# ------------------ TTS ------------------
def clean_for_tts(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"[#>\[\]\(\)\{\}_`~^=|\\/@]", " ", t)
    t = re.sub(r"[:;,.!?…“”\"'’\-–—]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tts_bytes(text: str) -> bytes:
    safe = clean_for_tts(text)
    if not safe:
        safe = "Hazırım."
    if len(safe) > 1200:
        safe = safe[:1200] + " ..."
    mp3_fp = BytesIO()
    gTTS(safe, lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

# ------------------ Model ------------------
def system_prompt_meb_json():
    return """
Sen, özel öğrenme güçlüğü (ÖÖG) olan ortaokul öğrencisi için okuma yardımı yapan yardımcı öğretmensin.
Öğretim stratejin: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel).

AKIŞ:
1) Ön düzenleyici
2) Tam metin ekranda okunur
3) Kelime desteği (en fazla 3)
4) MEB tarzı A/B/C sorular (tam 6 soru)

SORU PAKETİ:
- 2 bilgi
- 1 cikarim
- 1 kelime
- 1 ana_fikir
- 1 baslik

ÇIKTI: SADECE JSON.

JSON:
{
  "acilis":"1-2 cümle",
  "kelime_destek":[{"kelime":"","anlam":""}],
  "sorular":[
    {"id":"Q1","tur":"bilgi|cikarim|ana_fikir|baslik|kelime",
     "kok":"","A":"","B":"","C":"","dogru":"A",
     "aciklama":"1 cümle","ipucu":"1 cümle"}
  ],
  "kisa_tekrar":"1 cümle"
}
"""

def safe_json_load(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            return json.loads(m.group(0))
        return {}

def ask_meb_activity(source_text: str) -> dict:
    user_prompt = f"KAYNAK METİN:\n{source_text}\n\nŞemaya göre JSON üret."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_meb_json()},
            {"role": "user", "content": user_prompt},
        ],
    )
    d = safe_json_load(resp.choices[0].message.content)
    d.setdefault("acilis", "Bugün metni okuyacağız ve sorularla anlayacağız.")
    d.setdefault("kelime_destek", [])
    d.setdefault("sorular", [])
    d.setdefault("kisa_tekrar", "Kısaca: Ana fikri bulduk ve soruları çözdük.")
    if isinstance(d.get("sorular"), list):
        d["sorular"] = d["sorular"][:6]
    else:
        d["sorular"] = []
    return d

# ------------------ PDF ------------------
def read_pdf_text(pdf_file) -> str:
    try:
        reader = PdfReader(pdf_file)
        txt_all = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                txt_all += t + "\n"
        return txt_all.strip()
    except Exception:
        return ""

def build_source_text(pdf_text: str, extra_text: str) -> str:
    src = ""
    if pdf_text.strip():
        src += pdf_text.strip() + "\n"
    if extra_text.strip():
        src += extra_text.strip() + "\n"
    return src.strip()

# ------------------ UI helpers ------------------
def card(title: str, body_html: str):
    st.markdown(
        f"""
<div class="card">
  <div class="badge">{title}</div>
  <div>{body_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def set_listen_text(text: str):
    st.session_state.last_listen_text = text

# =========================================================
# GİRİŞ
# =========================================================
if "user" not in st.session_state:
    st.markdown(
        """
        <div style="text-align:center; margin-top:60px;">
            <div style="font-size:52px; font-weight:900;">📚 Okuma Dostum</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    isim = st.text_input("Adını yaz", placeholder="Örn: Ali")
    sinif = st.selectbox("Sınıfını seç", ["5", "6", "7", "8"], index=0)

    if st.button("Giriş Yap", use_container_width=True) and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.sinif = sinif
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.pdf_text = ""
        st.session_state.extra_text = ""
        st.session_state.metin_kaynak = "MEB"
        st.session_state.metin_id = ""
        st.session_state.activity = None
        st.session_state.full_text = ""
        st.session_state.phase = "idle"   # idle | read | questions | done
        st.session_state.q_index = 0
        st.session_state.q_started_at = None
        st.session_state.hint_used = 0
        st.session_state.total_ipucu = 0
        st.session_state.total_time = 0.0
        st.session_state.correct_map = {}
        st.session_state.type_correct = {"ana_fikir": None, "cikarim": None}
        st.session_state.tts_used = 0
        st.session_state.mic_used = 0
        st.session_state.last_listen_text = ""
        st.session_state.show_mic = False
        st.rerun()

    with st.expander("❓ Chatbot nasıl kullanılır?"):
        st.markdown(
            """
- Öğretmen metni ekler (PDF / metin).
- Önce metni TAM görürsün ve okursun.
- Sonra A/B/C sorular gelir. Tıklayınca ilerlersin.
- 🎤 ile konuş, 🔊 ile dinle.
"""
        )
    st.stop()

# =========================================================
# ÜST
# =========================================================
st.markdown(
    f"""
<div style="text-align:center; margin-bottom:10px;">
  <div style="font-size:44px; font-weight:900;">📚 Okuma Dostum</div>
  <div style="font-size:18px; opacity:0.7;">{st.session_state.user} • {st.session_state.sinif}. Sınıf</div>
</div>
""",
    unsafe_allow_html=True,
)
col_exit = st.columns([8, 2])[1]
with col_exit:
    if st.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()
st.markdown("---")

# =========================================================
# SIDEBAR (metin yapıştır: Kaydet butonu -> ctrl+enter gerekmez)
# =========================================================
with st.sidebar:
    with st.expander("📄 PDF ekle", expanded=False):
        pdf_file = st.file_uploader("PDF seç", type="pdf", key="pdf_uploader")
        if pdf_file is not None:
            st.session_state.pdf_text = read_pdf_text(pdf_file)
            if st.session_state.pdf_text:
                st.success("PDF yüklendi ✔️")
            else:
                st.warning("PDF metni okunamadı (tarama PDF olabilir).")

    with st.expander("📝 Metin ekle", expanded=False):
        tmp = st.text_area("Metni buraya yapıştır", height=220, key="extra_text_tmp")
        if st.button("Metni Kaydet", use_container_width=True):
            st.session_state.extra_text = tmp
            st.success("Metin kaydedildi ✔️")

    with st.expander("🏷️ Metin bilgisi (tez için)", expanded=False):
        st.session_state.metin_kaynak = st.selectbox("Metin Kaynak", ["MEB", "Diğer"], index=0)
        st.session_state.metin_id = st.text_input("Metin ID", placeholder="Örn: 6.sınıf Ünite2 Metin3")

pdf_text = st.session_state.get("pdf_text", "")
extra_text = st.session_state.get("extra_text", "")
metin_kaynak = st.session_state.get("metin_kaynak", "MEB")
metin_id = st.session_state.get("metin_id", "")

# =========================================================
# AKTİVİTE
# =========================================================
def start_activity():
    source_text = build_source_text(pdf_text, extra_text)
    if not source_text:
        source_text = "Kısa bir bilgilendirici metin üret ve okuma etkinliği yap."
    activity = ask_meb_activity(source_text)

    st.session_state.activity = activity
    st.session_state.full_text = source_text
    st.session_state.phase = "read"
    st.session_state.q_index = 0
    st.session_state.q_started_at = None
    st.session_state.hint_used = 0
    st.session_state.total_ipucu = 0
    st.session_state.total_time = 0.0
    st.session_state.correct_map = {}
    st.session_state.type_correct = {"ana_fikir": None, "cikarim": None}

    set_listen_text(activity.get("acilis", ""))

def go_questions():
    st.session_state.phase = "questions"
    st.session_state.q_index = 0
    st.session_state.q_started_at = time.time()
    st.session_state.hint_used = 0

def process_choice(chosen: str):
    activity = st.session_state.activity
    sorular = activity.get("sorular", [])
    idx = st.session_state.q_index
    if idx >= len(sorular):
        return

    q = sorular[idx]
    dogru = q.get("dogru", "A")
    aciklama = q.get("aciklama", "")

    started = st.session_state.q_started_at or time.time()
    sure = round(time.time() - started, 2)
    st.session_state.total_time += sure

    dogru_mu = 1 if chosen == dogru else 0
    st.session_state.correct_map[q.get("id", f"Q{idx+1}")] = dogru_mu

    if q.get("tur") == "ana_fikir":
        st.session_state.type_correct["ana_fikir"] = dogru_mu
    if q.get("tur") == "cikarim":
        st.session_state.type_correct["cikarim"] = dogru_mu

    feedback = "Doğru." if dogru_mu else f"Yanlış. Doğru cevap {dogru}."
    set_listen_text((feedback + " " + (aciklama or "")).strip())

    st.session_state.q_index += 1
    st.session_state.q_started_at = time.time()
    st.session_state.hint_used = 0

def render_read_phase(activity: dict, full_text: str):
    acilis = activity.get("acilis", "Bugün metni okuyacağız.")
    card("Önce hedefi bilelim", acilis)
    set_listen_text(acilis)

    card("Şimdi metni oku", f"<div style='white-space:pre-wrap;'>{full_text}</div>")

    col1, col2 = st.columns([2, 2])
    with col1:
        if st.button("✅ Metni okudum, sorulara geç", use_container_width=True):
            go_questions()
            st.rerun()
    with col2:
        if st.button("🔊 Metni dinle (kısa)", use_container_width=True):
            st.session_state.tts_used = 1
            st.audio(tts_bytes(full_text[:1200]), format="audio/mp3")

def render_questions_phase(activity: dict):
    kel = activity.get("kelime_destek", [])
    if kel:
        lines = "<br>".join([f"• <b>{k.get('kelime','')}</b>: {k.get('anlam','')}" for k in kel[:3]])
        card("Kelime desteği", lines)

    sorular = activity.get("sorular", [])
    idx = st.session_state.q_index
    if idx >= len(sorular):
        toplam = len(sorular)
        dogru = sum(int(v) for v in st.session_state.correct_map.values()) if st.session_state.correct_map else 0
        yuzde = round((dogru / toplam) * 100, 1) if toplam else 0.0
        ort_sure = round(st.session_state.total_time / toplam, 2) if toplam else 0.0

        card("Bitti ✅", f"Toplam soru: <b>{toplam}</b><br>Doğru: <b>{dogru}</b><br>Başarı: <b>%{yuzde}</b><br>Ortalama süre: <b>{ort_sure} sn</b>")
        card("Kısa tekrar", activity.get("kisa_tekrar",""))
        set_listen_text(activity.get("kisa_tekrar",""))
        st.session_state.phase = "done"
        return

    q = sorular[idx]
    kok = q.get("kok","")
    A, B, C = q.get("A",""), q.get("B",""), q.get("C","")
    dogru = q.get("dogru","A")
    aciklama = q.get("aciklama","")
    ipucu = q.get("ipucu","")

    set_listen_text(f"{kok}. A {A}. B {B}. C {C}.")

    card("Soru", f"<b>{idx+1}/{len(sorular)}</b> • <b>{kok}</b><br><br>A) {A}<br>B) {B}<br>C) {C}")

    if st.button("💡 İpucu", use_container_width=True):
        st.session_state.hint_used += 1
        st.session_state.total_ipucu += 1
        st.info(ipucu if ipucu else "Metne dön. Metnin tamamını kapsayan seçeneği düşün.")

    colA, colB, colC = st.columns(3)
    chosen = None
    with colA:
        if st.button("A", use_container_width=True):
            chosen = "A"
    with colB:
        if st.button("B", use_container_width=True):
            chosen = "B"
    with colC:
        if st.button("C", use_container_width=True):
            chosen = "C"

    if chosen:
        process_choice(chosen)
        if chosen == dogru:
            st.success("Doğru ✅")
        else:
            st.warning(f"Yanlış. Doğru cevap: {dogru}")
        if aciklama:
            st.caption(aciklama)
        st.rerun()

# =========================================================
# GÖRÜNTÜLEME
# =========================================================
if not st.session_state.get("activity"):
    card("Başlangıç", "Önce metni ekleyin. Sonra aşağıdan <b>Başla</b> deyin.")
else:
    if st.session_state.phase == "read":
        render_read_phase(st.session_state.activity, st.session_state.get("full_text",""))
    elif st.session_state.phase == "questions":
        render_questions_phase(st.session_state.activity)
    elif st.session_state.phase == "done":
        card("Yeni metin", "Yeni metin ekleyip tekrar <b>Başla</b> diyebilirsin.")

# =========================================================
# ALT BAR: Enter ile gönder (FORM) + Mikrofon + Dinle + Başla
# - clear_on_submit=True -> draft hatası yok
# =========================================================
c1, c2, c3, c4 = st.columns([8, 1.2, 1.2, 2.2])

with c1:
    with st.form("quick_note_form", clear_on_submit=True):
        note = st.text_input("", placeholder="Buraya yaz ve Enter'a bas (not)", label_visibility="collapsed")
        submitted = st.form_submit_button("Gönder")
        if submitted and note.strip():
            # sadece not olarak kaydetmek istersen
            sheet_append_safe(chat_sheet, [
                st.session_state.session_id,
                st.session_state.user,
                now_tr_str(),
                st.session_state.sinif,
                metin_kaynak,
                metin_id,
                "user",
                note.strip(),
                "", "", "", "", "", "", "", "", "", "", "", "", ""
            ])

with c2:
    if st.button("🎤", use_container_width=True):
        st.session_state.show_mic = not st.session_state.get("show_mic", False)

with c3:
    if st.button("🔊", use_container_width=True):
        t = st.session_state.get("last_listen_text", "")
        if t.strip():
            st.session_state.tts_used = 1
            st.audio(tts_bytes(t), format="audio/mp3")
        else:
            st.warning("Dinlenecek bir şey yok.")

with c4:
    if st.button("Başla", use_container_width=True):
        start_activity()
        st.rerun()

# Mikrofon paneli
if st.session_state.get("show_mic", False):
    st.markdown("---")
    card("🎤 Mikrofon", "Konuş → durdur. (Sorudayken A/B/C dersen şık seçer.)")
    audio_bytes = audio_recorder(
        text="Konuş",
        pause_threshold=1.8,
        sample_rate=16000,
        key="mic_panel",
    )
    if audio_bytes:
        st.session_state.mic_used = 1
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="tr",
                )
            mic_text = (transcript.text or "").strip()
            if mic_text:
                st.info(f"Sesli: **{mic_text}**")
        except Exception as e:
            st.error(f"Ses yazıya çevrilemedi: {e}")
