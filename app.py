import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from openai import OpenAI
import tempfile
from audio_recorder_streamlit import audio_recorder
import re
from collections import Counter
from gtts import gTTS
from io import BytesIO
import json

# =========================================================
# OKUMA DOSTUM — ÖÖG + Sunuş Yoluyla (Metinden okuma → ana fikir → sorular)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide", initial_sidebar_state="expanded")

# ------------------ ÖÖG DOSTU CSS (BÜYÜK PUNTO + BOŞLUK) ------------------
st.markdown(
    """
<style>
/* GENEL (ÖÖG) */
html, body, [class*="css"] { font-size: 20px !important; }
p, li, div, span { line-height: 1.9 !important; }
.stChatMessage p { font-size: 20px !important; line-height: 1.9 !important; }

/* INPUT/TEXTAREA */
.stTextInput input, .stTextArea textarea {
  font-size: 20px !important;
  line-height: 1.9 !important;
  padding: 14px 14px !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
  font-size: 18px !important;
  opacity: .65;
}

/* BUTON */
.stButton button{
  font-size: 18px !important;
  border-radius: 16px !important;
  padding: 10px 14px !important;
}

/* Okunabilirlik boşluk */
.stMarkdown { word-spacing: 0.16em !important; letter-spacing: 0.02em !important; }

/* Üst boşluk: başlık kırpılmasın */
.block-container { padding-top: 1.6rem; padding-bottom: 2.0rem; max-width: none; }

/* Kart */
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:18px;
  padding:16px 18px;
  margin:12px 0;
  background: rgba(255,255,255,.92);
}
.badge{
  display:inline-block;
  padding:6px 12px;
  border-radius:999px;
  border:1px solid rgba(0,0,0,.12);
  font-size:16px;
  opacity:.85;
  margin-bottom:10px;
}

/* Başlık sınıfı (responsive, asla kaybolmasın) */
.app-title{
  text-align:center;
  font-weight:900;
  font-size: clamp(22px, 3.2vw, 38px);
  line-height: 1.15;
  white-space: nowrap;
}

/* Alt bar */
.bottombar{
  position: sticky;
  bottom: 0;
  background: rgba(255,255,255,0.94);
  border-top: 1px solid rgba(0,0,0,0.08);
  padding: 12px 0 8px 0;
  backdrop-filter: blur(6px);
}
.smallhint{ font-size: 14px; opacity: .7; }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------ OPENAI CLIENT ------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ GOOGLE SHEETS ------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
gc = gspread.authorize(credentials)
workbook = gc.open_by_url(st.secrets["GSHEET_URL"])

stats_sheet = workbook.sheet1
try:
    chat_sheet = workbook.worksheet("Sohbet")
except WorksheetNotFound:
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=2000, cols=4)
    chat_sheet.append_row(["Kullanici", "Zaman", "Rol", "Mesaj"])


def log_message(user, role, content):
    try:
        now_tr = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")
        chat_sheet.append_row([user, now_tr, role, content])
    except Exception as e:
        st.error(f"Sohbet kaydedilirken hata: {e}")


def load_history(user):
    messages = []
    try:
        rows = chat_sheet.get_all_records()
        for r in rows:
            if r.get("Kullanici") == user:
                role = "user" if str(r.get("Rol", "")).lower() == "user" else "assistant"
                content = r.get("Mesaj", "")
                if content:
                    messages.append({"role": role, "content": content})
    except Exception as e:
        st.error(f"Sohbet geçmişi yüklenemedi: {e}")
    return messages


def kelime_istatistikleri(metinler):
    if not metinler:
        return "", ""
    text = " ".join(metinler).lower()
    tokens = re.findall(r"\w+", text, flags=re.UNICODE)
    stop = {
        "ve","veya","ile","ama","fakat","çünkü","ben","sen","o","biz","siz","onlar",
        "bu","şu","bir","iki","üç","mi","mı","mu","mü","de","da","ki","için","gibi",
        "çok","az","ne","neden","nasıl","hangi"
    }
    words = [t for t in tokens if len(t) > 2 and t not in stop]
    if not words:
        return "", ""
    counts = Counter(words)
    en_cok, _ = counts.most_common(1)[0]
    top5 = ", ".join([f"{w} ({c})" for w, c in counts.most_common(5)])
    return en_cok, top5


def oturum_ozeti_yaz():
    if "user" not in st.session_state or "start_time" not in st.session_state:
        return
    now_tr = datetime.now(ZoneInfo("Europe/Istanbul"))
    start = st.session_state.start_time
    dakika = round((now_tr - start).total_seconds() / 60, 1)
    giris_str = start.strftime("%d.%m.%Y %H:%M:%S")
    cikis_str = now_tr.strftime("%d.%m.%Y %H:%M:%S")
    en_cok, diger = kelime_istatistikleri(st.session_state.get("user_texts", []))
    try:
        stats_sheet.append_row([st.session_state.user, giris_str, cikis_str, dakika, en_cok, diger])
    except Exception as e:
        st.error(f"Oturum özeti yazılırken hata: {e}")


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


# ------------------ MODEL ------------------
def system_prompt_json():
    return """
Sen, özel öğrenme güçlüğü olan (ÖÖG) ortaokul öğrencisi için derste kullanılan yardımcı öğretim materyalisisin.
Öğretim stratejin: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel).

- Uzun paragraf yok.
- Kısa cümle, basit kelime.
- A/B/C sorular üret.
- Metin varsa metne dayan.
- Akademik etiket yazma.
- Metni 2-4 kısa parçaya böl.

ÇIKTI: SADECE JSON.

JSON:
{
  "acilis": "1-2 cümle",
  "parcalar": [
    {"metin":"kısa parça", "soru1":"kısa", "soru2":"kısa"}
  ],
  "ana_fikir": {"soru":"...", "A":"...", "B":"...", "C":"...", "dogru":"A"},
  "metin_sorusu": {"soru":"...", "A":"...", "B":"...", "C":"...", "dogru":"B"},
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


def ask_model(lesson_goal: str, source_text: str) -> dict:
    prompt = (
        f"HEDEF: {lesson_goal}\n\n"
        f"KAYNAK METİN:\n{source_text}\n\n"
        "Metni 2-4 parçaya böl. Parça soruları çok kısa olsun."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_json()},
            {"role": "user", "content": prompt},
        ],
    )
    d = safe_json_load(resp.choices[0].message.content)
    d.setdefault("acilis", "Bugün metni birlikte okuyacağız ve ana fikri bulacağız.")
    d.setdefault("parcalar", [])
    d.setdefault("ana_fikir", {"soru": "Ana fikir hangisi?", "A": "", "B": "", "C": "", "dogru": "A"})
    d.setdefault("metin_sorusu", {"soru": "Metne göre hangisi doğru?", "A": "", "B": "", "C": "", "dogru": "A"})
    d.setdefault("kisa_tekrar", "Kısaca: Ana fikir metnin en önemli mesajıdır.")
    if isinstance(d.get("parcalar"), list):
        d["parcalar"] = d["parcalar"][:4]
    else:
        d["parcalar"] = []
    return d


def make_card(title, body_html):
    st.markdown(
        f"""
<div class="card">
  <div class="badge">{title}</div>
  <div>{body_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def build_source_text(pdf_text: str, extra_text: str) -> str:
    src = ""
    if pdf_text.strip():
        src += pdf_text.strip() + "\n"
    if extra_text.strip():
        src += extra_text.strip() + "\n"
    return src.strip()


def show_lesson(d: dict):
    make_card("Başlayalım", d.get("acilis", ""))
    for i, p in enumerate(d.get("parcalar", []), start=1):
        make_card(
            f"Okuma parçası {i}",
            f"{p.get('metin','')}<br><br>• {p.get('soru1','')}<br>• {p.get('soru2','')}",
        )
    af = d.get("ana_fikir", {})
    make_card(
        "Ana fikir seç",
        f"<b>{af.get('soru','')}</b><br><br>"
        f"A) {af.get('A','')}<br>"
        f"B) {af.get('B','')}<br>"
        f"C) {af.get('C','')}",
    )
    ms = d.get("metin_sorusu", {})
    make_card(
        "Metinden soru",
        f"<b>{ms.get('soru','')}</b><br><br>"
        f"A) {ms.get('A','')}<br>"
        f"B) {ms.get('B','')}<br>"
        f"C) {ms.get('C','')}",
    )
    make_card("Kısa tekrar", d.get("kisa_tekrar", ""))


def start_lesson(lesson_goal: str, pdf_text: str, extra_text: str):
    source_text = build_source_text(pdf_text, extra_text)
    if not source_text:
        source_text = "Metin yok. Kısa bir metin uydurarak ana fikir çalışması yaptır."

    with st.chat_message("user"):
        st.write(lesson_goal)

    st.session_state.messages.append({"role": "user", "content": lesson_goal})
    st.session_state.user_texts.append(lesson_goal)
    log_message(st.session_state.user, "user", lesson_goal)

    d = ask_model(lesson_goal, source_text)
    st.session_state.last_lesson = d
    st.session_state.last_assistant_text = (d.get("acilis","") + " " + d.get("kisa_tekrar","")).strip()

    st.session_state.messages.append({"role": "assistant", "content": d.get("kisa_tekrar", "")})
    log_message(st.session_state.user, "assistant", d.get("kisa_tekrar", ""))


# =========================================================
# 1) GİRİŞ EKRANI
# =========================================================
if "user" not in st.session_state:
    st.markdown(
        """
        <div style="text-align:center; margin-top:40px; margin-bottom:10px;">
            <div style="font-size:52px; font-weight:900;">📚 Okuma Dostum</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:10px; margin-top:22px; margin-bottom:8px;">
            <div style="font-size:28px;">👋</div>
            <div style="font-size:24px; font-weight:800;">Hoş geldiniz</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    isim = st.text_input("Adını yaz", placeholder="Örn: Ali")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        giris = st.button("Giriş Yap", use_container_width=True)

    if giris and isim.strip():
        isim = isim.strip()
        st.session_state.user = isim
        st.session_state.messages = load_history(isim)
        st.session_state.user_texts = []
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.session_state.last_audio_len = 0
        st.session_state.last_assistant_text = ""
        st.session_state.last_lesson = None
        st.session_state.draft = ""
        st.rerun()

    st.markdown("---")
    with st.expander("❓ Chatbot nasıl kullanılır?", expanded=False):
        st.markdown(
            """
**1) Öğretmen metni ekler**
- PDF yükler veya metni yapıştırır.

**2) Sen metni benimle okursun**
- Metni küçük parçalara bölerim.
- Her parçada iki kısa soru sorarım.

**3) Ana fikri buluruz**
- A/B/C ile seçersin.

**4) Metinden soru çözeriz**
- Okuduğunu anlama güçlenir.

**İpucu**
- 🎤 ile sesle sor.
- 🔊 ile dinle.
"""
        )
    st.stop()


# =========================================================
# 2) GİRİŞ SONRASI ANA EKRAN (BAŞLIK DAİMA GÖRÜNSÜN)
# =========================================================

# ÜST BAR
c_left, c_center, c_right = st.columns([2, 6, 2], vertical_alignment="top")

with c_left:
    st.markdown("### 📚")
    st.markdown(f"**{st.session_state.user}**")

with c_center:
    st.markdown('<div class="app-title">Okuma Dostum</div>', unsafe_allow_html=True)

with c_right:
    st.markdown("**Çıkış Paneli**")
    if st.button("Çıkış Yap", use_container_width=True):
        oturum_ozeti_yaz()
        st.session_state.clear()
        st.rerun()

st.markdown("---")

# SIDEBAR: iki panel
with st.sidebar:
    st.markdown("### 📌 Panel")
    with st.expander("📄 PDF Yükle", expanded=False):
        pdf_file = st.file_uploader("PDF seç", type="pdf", key="pdf_uploader")
        if pdf_file is not None:
            try:
                reader = PdfReader(pdf_file)
                txt_all = ""
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        txt_all += txt + "\n"
                st.session_state.pdf_text = txt_all.strip()
                st.success("PDF yüklendi ✔️")
            except Exception as e:
                st.error(f"PDF okunamadı: {e}")

    with st.expander("📝 Metin Yapıştır", expanded=False):
        st.session_state.extra_text = st.text_area("Metni buraya yapıştır", height=220, key="extra_text_area")

pdf_text = st.session_state.get("pdf_text", "")
extra_text = st.session_state.get("extra_text", "")

# SOHBET GEÇMİŞİ
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# DERS GÖRÜNTÜSÜ
if st.session_state.get("last_lesson"):
    with st.chat_message("assistant"):
        show_lesson(st.session_state.last_lesson)

# ALT BAR: mesaj + 🎤 + 🔊 + Gönder
st.markdown('<div class="bottombar"></div>', unsafe_allow_html=True)
c_msg, c_mic, c_listen, c_send = st.columns([8, 1.2, 1.2, 1.8])

with c_msg:
    st.session_state.draft = st.text_area(
        "Mesaj",
        value=st.session_state.get("draft", ""),
        placeholder="Sorunu yaz (ör: Bu metnin ana fikrini bulalım)",
        label_visibility="collapsed",
        height=70,
        key="draft_input",
    )

with c_mic:
    with st.popover("🎤", use_container_width=True):
        st.markdown('<div class="smallhint">Konuş → durdur</div>', unsafe_allow_html=True)
        audio_bytes = audio_recorder(
            text="Konuş",
            pause_threshold=1.8,
            sample_rate=16000,
            key="mic_main",
        )
        if audio_bytes:
            last_len = st.session_state.get("last_audio_len", 0)
            if len(audio_bytes) != last_len:
                st.session_state["last_audio_len"] = len(audio_bytes)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="tr",
                    )
                mic_text = transcript.text.strip()
                if mic_text:
                    start_lesson(mic_text, pdf_text, extra_text)
                    st.rerun()

with c_listen:
    if st.button("🔊", use_container_width=True):
        t = st.session_state.get("last_assistant_text", "")
        if t.strip():
            st.audio(tts_bytes(t), format="audio/mp3")
        else:
            st.warning("Dinlenecek bir şey yok.")

with c_send:
    if st.button("Gönder", use_container_width=True):
        msg = st.session_state.get("draft_input", "").strip()
        if msg:
            start_lesson(msg, pdf_text, extra_text)
            st.session_state.draft = ""
            st.rerun()
