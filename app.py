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
# OKUMA DOSTUM — ÖÖG & MEB DESTEKLİ SİSTEM
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide", initial_sidebar_state="expanded")

# ÖÖG Dostu Görsel Ayarlar (Geniş boşluklar, okunaklı fontlar)
st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 22px !important; }
p, li, div, span { line-height: 2.0 !important; }
.stChatMessage p { font-size: 22px !important; line-height: 2.0 !important; }
.stTextInput input, .stTextArea textarea {
  font-size: 20px !important; line-height: 1.8 !important; padding: 15px !important;
}
.stButton button{ font-size: 20px !important; border-radius: 20px !important; padding: 12px 20px !important; font-weight: bold !important; }
.stMarkdown { word-spacing: 0.20em !important; letter-spacing: 0.03em !important; }
.block-container { padding-top: 2rem; max-width: 1000px; margin: auto; }
.card{
  border: 2px solid #e0e0e0;
  border-radius: 20px; padding: 20px; margin: 15px 0;
  background: #ffffff;
  box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}
.badge{
  display:inline-block; padding:8px 16px; border-radius:12px;
  background: #f0f2f6; color: #1f77b4; font-weight: bold; margin-bottom:12px;
}
.highlight-text {
    background-color: #fcfcfc;
    padding: 25px;
    border-left: 10px solid #ff4b4b;
    border-radius: 10px;
    font-size: 24px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ Sheets Bağlantısı ------------------
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
        st.error(f"Kayıt hatası: {e}")

# ------------------ Ses ve Metin İşleme ------------------
def clean_for_tts(text: str) -> str:
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    t = re.sub(r"[#>\[\]\(\)\{\}_`~^=|\\/@]", " ", t)
    return t.strip()

def tts_bytes(text: str) -> bytes:
    safe = clean_for_tts(text)
    mp3_fp = BytesIO()
    gTTS(safe[:1200], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

# ------------------ AI Zekası (ÖÖG Odaklı) ------------------
def system_prompt_meb_json():
    return """
Sen, özel öğrenme güçlüğü (disleksi vb.) olan ortaokul öğrencileri için materyal düzenleyen uzman bir öğretmensin.
SUNUŞ YOLUYLA ÖĞRETİM stratejisini kullan.

GÖREVİN:
1) 'duzenlenmis_metin': Kaynak metni öğrencinin okuyabileceği hale getir. Cümleleri çok kısa tut. Karmaşık kelimeleri basitleştir.
2) 'kelime_destek': Metindeki en önemli 3 kelimeyi ve çocuksu/basit anlamlarını yaz.
3) 'sorular': 6 adet çoktan seçmeli (A, B, C) soru hazırla. Sorular net ve kısa olsun.

ÇIKTI SADECE JSON.
JSON YAPISI:
{
  "acilis": "Motivasyon cümlesi",
  "duzenlenmis_metin": "Sadeleştirilmiş, kısa cümleli metin",
  "kelime_destek": [{"kelime":"", "anlam":""}],
  "sorular": [
    {"id":"Q1", "tur":"bilgi|cikarim|ana_fikir|baslik|kelime", "kok":"", "A":"", "B":"", "C":"", "dogru":"A", "aciklama":"", "ipucu":""}
  ],
  "kisa_tekrar": "Özet cümle"
}
"""

def safe_json_load(raw: str) -> dict:
    try:
        return json.loads(re.search(r"\{.*\}", raw, flags=re.S).group(0))
    except:
        return {}

def ask_meb_activity(source_text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o", # Daha iyi analiz için gpt-4o önerilir
        messages=[
            {"role": "system", "content": system_prompt_meb_json()},
            {"role": "user", "content": f"Şu metni öğrenci için işle:\n\n{source_text}"},
        ],
        temperature=0.3
    )
    d = safe_json_load(resp.choices[0].message.content)
    return d

# ------------------ Dosya ve Metin Fonksiyonları ------------------
def read_pdf_text(pdf_file) -> str:
    try:
        reader = PdfReader(pdf_file)
        return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    except:
        return ""

# =========================================================
# ARA YÜZ VE MANTIĞI
# =========================================================
if "user" not in st.session_state:
    st.markdown("<h1 style='text-align:center;'>📚 Okuma Dostum</h1>", unsafe_allow_html=True)
    isim = st.text_input("Adın nedir?")
    sinif = st.selectbox("Sınıfın?", ["5", "6", "7", "8"])
    if st.button("Başla!", use_container_width=True) and isim:
        st.session_state.user = isim
        st.session_state.sinif = sinif
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.phase = "idle"
        st.rerun()
    st.stop()

# Üst Panel
st.markdown(f"### Merhaba {st.session_state.user}! Bugün ne okuyoruz?")

# Sidebar: Metin Yükleme
with st.sidebar:
    st.title("Öğretmen Paneli")
    pdf_file = st.file_uploader("MEB Kitabı PDF Yükle", type="pdf")
    extra_text = st.text_area("Veya Metni Buraya Yapıştır", height=200)
    
    if st.button("Metni Sisteme Yükle"):
        raw_text = extra_text
        if pdf_file:
            raw_text = read_pdf_text(pdf_file) + "\n" + extra_text
        
        with st.spinner("Öğrenciye göre düzenleniyor..."):
            activity = ask_meb_activity(raw_text)
            st.session_state.activity = activity
            st.session_state.full_text = activity.get("duzenlenmis_metin", raw_text)
            st.session_state.phase = "read"
            st.session_state.q_index = 0
            st.session_state.correct_map = {}
            st.session_state.last_listen_text = activity.get("acilis", "")
            st.success("Metin hazır!")
            st.rerun()
    
    if st.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

# ------------------ EKRANLAR (PHASES) ------------------

# 1. OKUMA EKRANI
if st.session_state.get("phase") == "read":
    act = st.session_state.activity
    st.info(f"🎯 Hedef: {act.get('acilis')}")
    
    st.markdown(f"<div class='highlight-text'>{st.session_state.full_text}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔊 Metni Dinle", use_container_width=True):
            st.audio(tts_bytes(st.session_state.full_text))
    with c2:
        if st.button("✅ Okudum, Sorulara Geç", use_container_width=True):
            st.session_state.phase = "questions"
            st.session_state.q_started_at = time.time()
            st.rerun()

# 2. SORU EKRANI
elif st.session_state.get("phase") == "questions":
    act = st.session_state.activity
    sorular = act.get("sorular", [])
    idx = st.session_state.q_index

    if idx < len(sorular):
        q = sorular[idx]
        
        # Kelime desteğini göster
        if idx == 0 and act.get("kelime_destek"):
            with st.expander("💡 Önemli Kelimeler", expanded=True):
                for k in act["kelime_destek"]:
                    st.write(f"**{k['kelime']}**: {k['anlam']}")

        st.markdown(f"### Soru {idx+1}/{len(sorular)}")
        st.markdown(f"<div class='card'>{q['kok']}</div>", unsafe_allow_html=True)
        
        colA, colB, colC = st.columns(3)
        for label, col in zip(["A", "B", "C"], [colA, colB, colC]):
            with col:
                if st.button(f"{label}) {q[label]}", use_container_width=True):
                    # Cevap kontrolü
                    is_correct = 1 if label == q["dogru"] else 0
                    st.session_state.correct_map[idx] = is_correct
                    
                    if is_correct:
                        st.balloons()
                        st.success("Harikasın! Doğru.")
                    else:
                        st.error(f"Üzülme, doğru cevap {q['dogru']}. {q['aciklama']}")
                    
                    time.sleep(2)
                    st.session_state.q_index += 1
                    st.rerun()
        
        if st.button("💡 İpucu Al"):
            st.info(q.get("ipucu", "Metne tekrar bakmayı dene!"))
    else:
        st.session_state.phase = "done"
        st.rerun()

# 3. BİTİŞ EKRANI
elif st.session_state.get("phase") == "done":
    st.success("Tebrikler! Çalışmayı tamamladın.")
    dogru_sayisi = sum(st.session_state.correct_map.values())
    st.metric("Doğru Sayısı", f"{dogru_sayisi} / 6")
    
    # Sheets'e performans kaydet
    if st.button("Yeni Metne Geç"):
        st.session_state.phase = "idle"
        st.rerun()

# Alt Çubuk (Mikrofon ve Notlar)
if st.session_state.get("user"):
    st.markdown("---")
    c1, c2, c3 = st.columns([6, 2, 2])
    with c1:
        note = st.text_input("Bir notun var mı?", key="user_note")
    with c2:
        if st.button("🔊 Dinle", use_container_width=True):
            st.audio(tts_bytes(st.session_state.get("last_listen_text", "Harika gidiyorsun!")))
    with c3:
         # Basit mikrofon tetikleyici (Geliştirilebilir)
         st.write("🎤 Sesli komut aktif")
