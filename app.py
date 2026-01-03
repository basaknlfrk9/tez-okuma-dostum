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

# ------------------ SAYFA AYARI ------------------
st.set_page_config(page_title="Okuma Dostum", layout="wide")
st.title("📚 Okuma Dostum")

# ------------------ ÖÖG DOSTU CSS (BÜYÜK PUNTO + BOŞLUK) ------------------
st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 22px !important; }
p, li, div, span { line-height: 1.8 !important; }
.stChatMessage p { font-size: 22px !important; line-height: 1.8 !important; }
.stTextInput input, .stTextArea textarea { font-size: 22px !important; line-height: 1.8 !important; }
.stMarkdown { word-spacing: 0.10em !important; letter-spacing: 0.01em !important; }

/* Kart */
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:16px;
  padding:14px 16px;
  margin:10px 0;
  background: rgba(255,255,255,.80);
}
.badge{
  display:inline-block;
  padding:4px 10px;
  border-radius:999px;
  border:1px solid rgba(0,0,0,.12);
  font-size:16px;
  opacity:.85;
  margin-bottom:8px;
}

/* Alt bar (mikrofon + yardım + dinle) gibi dursun diye daha sıkı */
.bottombar { margin-top: 10px; margin-bottom: 6px; }

/* Butonların fazla büyümemesi */
.stButton button{ border-radius:14px !important; padding:8px 12px !important; }

/* Sayfayı ferah yap */
.block-container { padding-top: 1.1rem; padding-bottom: 2.2rem; max-width: 980px; }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------ OPENAI ------------------
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
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=1000, cols=4)
    chat_sheet.append_row(["Kullanici", "Zaman", "Rol", "Mesaj"])

# ------------------ SHEETS UTIL ------------------
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

# ------------------ TTS (NOKTALAMA OKUMASIN) ------------------
def clean_for_tts(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)  # markdown bold
    t = re.sub(r"[#>\[\]\(\)\{\}_`~^=|\\/@]", " ", t)
    t = re.sub(r"[:;,.!?…“”\"'’\-–—]", " ", t)  # noktalama
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

# ------------------ SUNUŞ YOLUYLA ÖĞRETİM (ÇOCUK DİLİ, ETİKET YOK) ------------------
def system_prompt_json():
    return """
Sen, özel öğrenme güçlüğü olan ortaokul öğrencisi için derste yardımcı materyal olan bir öğretim chatbotusun.
Öğretim stratejin: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel).

KURAL:
- Öğrenciyi keşfe bırakma.
- Uzun paragraf yok.
- Basit kelime.
- Kısa cümle.
- Öğrenci yazmakta zorlanabilir: seçenekli sorular kullan.

ÇIKTI: SADECE JSON. Başka hiçbir şey yazma.

ÖNEMLİ:
- Basamak isimlerini akademik yazma.
- "görsel benzetme" gibi terimler yazma.
- Basamak başlıkları çocuk diliyle olsun.

JSON ŞEMASI:
{
  "adim1": {"baslik": "1) Başla", "metin": "Dikkat çeken 1-2 cümle"},
  "adim2": {"baslik": "2) Kısa anlat", "maddeler": ["madde1","madde2","madde3"]},
  "adim3": {"baslik": "3) Örnek göster", "adimlar": ["adım1","adım2"]},
  "adim4": {"baslik": "4) Sen dene", "soru": "A/B/C seçmeli soru", "A": "A", "B": "B", "C": "C", "dogru": "A"},
  "adim5": {"baslik": "5) Tekrar", "metin": "1 cümle özet"},
  "adim6": {"baslik": "6) Kontrol", "soru": "1 kısa kontrol sorusu"},
  "geribildirim": {"dogru": "1 cümle", "yanlis": "1 cümle"}
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

def format_for_history(d: dict) -> str:
    # Kaydetmek için sade metin
    out = []
    for key in ["adim1","adim2","adim3","adim4","adim5","adim6"]:
        a = d.get(key, {})
        if not a:
            continue
        baslik = a.get("baslik", key)
        out.append(baslik)
        if "metin" in a and a["metin"]:
            out.append(a["metin"])
        if "maddeler" in a and a["maddeler"]:
            out.extend([f"- {x}" for x in a["maddeler"]])
        if "adimlar" in a and a["adimlar"]:
            out.extend([f"{i+1}) {x}" for i, x in enumerate(a["adimlar"])])
        if key == "adim4":
            out.append(a.get("soru",""))
            out.append(f"A) {a.get('A','')}")
            out.append(f"B) {a.get('B','')}")
            out.append(f"C) {a.get('C','')}")
    return "\n".join([x for x in out if x])

def ask_model(user_question: str, pdf_text: str, extra_text: str) -> dict:
    # PDF/metin varsa "metinden öğretim" gibi kullan
    content = ""
    if pdf_text:
        content += "PDF:\n" + pdf_text[:900] + "\n\n"
    if extra_text:
        content += "Metin:\n" + extra_text[:900] + "\n\n"

    prompt = f"SORU/KONU: {user_question}\n\n"
    if content:
        prompt += "KAYNAK METİN VAR. Bu metne dayanarak anlat.\n\n" + content
    else:
        prompt += "KAYNAK METİN YOK. Konuyu anlat.\n"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_json()},
            {"role": "user", "content": prompt},
        ],
    )
    d = safe_json_load(resp.choices[0].message.content)

    # Eksikleri doldur
    d.setdefault("adim1", {"baslik":"1) Başla","metin":"Hazır mısın?"})
    d.setdefault("adim2", {"baslik":"2) Kısa anlat","maddeler":[]})
    d.setdefault("adim3", {"baslik":"3) Örnek göster","adimlar":[]})
    d.setdefault("adim4", {"baslik":"4) Sen dene","soru":"","A":"","B":"","C":"","dogru":"A"})
    d.setdefault("adim5", {"baslik":"5) Tekrar","metin":""})
    d.setdefault("adim6", {"baslik":"6) Kontrol","soru":""})
    d.setdefault("geribildirim", {"dogru":"Aferin! Doğru seçtin.","yanlis":"Sorun değil. İpucuna bakalım."})
    return d

def show_steps(d: dict, reveal: int):
    # 1-6 adımı sırayla göster
    if reveal >= 1:
        a = d["adim1"]
        make_card(a.get("baslik","1) Başla"), a.get("metin",""))
    if reveal >= 2:
        a = d["adim2"]
        maddeler = a.get("maddeler", [])[:5]
        body = "<br>".join([f"• {m}" for m in maddeler]) if maddeler else "• (Kısa bilgi)"
        make_card(a.get("baslik","2) Kısa anlat"), body)
    if reveal >= 3:
        a = d["adim3"]
        adimlar = a.get("adimlar", [])[:3]
        body = "<br>".join([f"{i+1}) {x}" for i, x in enumerate(adimlar)]) if adimlar else "1) (Örnek)"
        make_card(a.get("baslik","3) Örnek göster"), body)
    if reveal >= 4:
        a = d["adim4"]
        body = (
            f"<b>{a.get('soru','')}</b><br><br>"
            f"A) {a.get('A','')}<br>"
            f"B) {a.get('B','')}<br>"
            f"C) {a.get('C','')}"
        )
        make_card(a.get("baslik","4) Sen dene"), body)
    if reveal >= 5:
        a = d["adim5"]
        make_card(a.get("baslik","5) Tekrar"), a.get("metin",""))
    if reveal >= 6:
        a = d["adim6"]
        make_card(a.get("baslik","6) Kontrol"), a.get("soru",""))

def soruyu_isle(soru: str, pdf_text: str, extra_text: str):
    with st.chat_message("user"):
        st.write(soru)

    st.session_state.messages.append({"role": "user", "content": soru})
    st.session_state.user_texts.append(soru)
    st.session_state.last_user_text = soru
    log_message(st.session_state.user, "user", soru)

    with st.chat_message("assistant"):
        d = ask_model(soru, pdf_text, extra_text)
        st.session_state.last_lesson = d
        st.session_state.reveal = 1

        # İlk anda sadece 1. adım göster (çocuk için az yük)
        show_steps(d, reveal=1)

        history_text = format_for_history(d)
        st.session_state.last_assistant_text = history_text
        st.session_state.messages.append({"role": "assistant", "content": history_text})
        log_message(st.session_state.user, "assistant", history_text)

# ------------------ GİRİŞ ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.messages = load_history(st.session_state.user)

        st.session_state.user_texts = []
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.session_state.last_user_text = ""
        st.session_state.last_assistant_text = ""
        st.session_state.last_lesson = None
        st.session_state.reveal = 0
        st.session_state.last_audio_len = 0

        # Giriş yönergesi (net, kısa)
        if not st.session_state.messages:
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "✅ **Nasıl kullanılır?**\n"
                    "- Sorunu alttan yaz.\n"
                    "- 🎤 ile sesle sor.\n"
                    "- Ben **adım adım** anlatırım.\n"
                    "- 🆘 ile yardım/SSS açılır.\n"
                )
            })
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    # Üst bar: sadece çıkış
    top1, top2 = st.columns([3, 1])
    with top1:
        st.success(f"Hoş geldin 🌈 {st.session_state.user}")
    with top2:
        if st.button("Çıkış", use_container_width=True):
            oturum_ozeti_yaz()
            st.session_state.clear()
            st.rerun()

    # PDF/metin: öğretmen kullanacak; sade bir expander
    with st.expander("📄 Öğretmen: PDF / Metin ekle (istersen)", expanded=False):
        c1, c2 = st.columns(2)
        pdf_text = ""
        extra_text = ""
        with c1:
            pdf_file = st.file_uploader("PDF seç", type="pdf")
            if pdf_file is not None:
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        pdf_text += txt + "\n"
        with c2:
            extra_text = st.text_area("Metni buraya yapıştır", height=160)

    pdf_text = locals().get("pdf_text", "")
    extra_text = locals().get("extra_text", "")

    # Sohbet geçmişi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # Adım adım kontrol (çok sade)
    d = st.session_state.get("last_lesson")
    if d:
        st.markdown("### ✅ Adım adım")
        b1, b2, b3, b4, b5, b6 = st.columns(6)
        with b1:
            if st.button("1", use_container_width=True): st.session_state.reveal = 1
        with b2:
            if st.button("2", use_container_width=True): st.session_state.reveal = max(st.session_state.reveal, 2)
        with b3:
            if st.button("3", use_container_width=True): st.session_state.reveal = max(st.session_state.reveal, 3)
        with b4:
            if st.button("4", use_container_width=True): st.session_state.reveal = max(st.session_state.reveal, 4)
        with b5:
            if st.button("5", use_container_width=True): st.session_state.reveal = max(st.session_state.reveal, 5)
        with b6:
            if st.button("6", use_container_width=True): st.session_state.reveal = max(st.session_state.reveal, 6)

        show_steps(d, st.session_state.reveal)

        # A/B/C seçim (sadece adım 4 açılınca)
        if st.session_state.reveal >= 4:
            a4 = d.get("adim4", {})
            choice = st.radio("Seç:", ["A", "B", "C"], horizontal=True, index=0, key="abc_choice")
            if st.button("Kontrol et", use_container_width=True):
                if choice == a4.get("dogru", "A"):
                    make_card("✅", d.get("geribildirim", {}).get("dogru", "Aferin!"))
                else:
                    make_card("🟡", d.get("geribildirim", {}).get("yanlis", "Sorun değil."))

    # ----- ALT BAR: 🎤 mikrofon (emoji) + 🔊 dinle + 🆘 yardım -----
    st.markdown('<div class="bottombar"></div>', unsafe_allow_html=True)
    c_mic, c_listen, c_help = st.columns([1, 1, 1])

    # 🎤 Mikrofon: chat alanının yanında küçük emoji gibi (popover varsa)
    with c_mic:
        try:
            with st.popover("🎤", use_container_width=True):
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
                        st.success("Ses alındı ✔️")

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            tmp.write(audio_bytes)
                            tmp_path = tmp.name

                        with open(tmp_path, "rb") as f:
                            transcript = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f,
                                language="tr",
                            )
                        mic_text = transcript.text
                        st.info(f"📝 {mic_text}")
                        soruyu_isle(mic_text, pdf_text, extra_text)
        except Exception:
            # popover yoksa expander
            with st.expander("🎤", expanded=False):
                audio_bytes = audio_recorder(
                    text="Konuş",
                    pause_threshold=1.8,
                    sample_rate=16000,
                    key="mic_main_fallback",
                )
                if audio_bytes:
                    last_len = st.session_state.get("last_audio_len", 0)
                    if len(audio_bytes) != last_len:
                        st.session_state["last_audio_len"] = len(audio_bytes)
                        st.success("Ses alındı ✔️")

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            tmp.write(audio_bytes)
                            tmp_path = tmp.name

                        with open(tmp_path, "rb") as f:
                            transcript = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f,
                                language="tr",
                            )
                        mic_text = transcript.text
                        st.info(f"📝 {mic_text}")
                        soruyu_isle(mic_text, pdf_text, extra_text)

    # 🔊 Dinle
    with c_listen:
        if st.button("🔊", use_container_width=True):
            t = st.session_state.get("last_assistant_text", "")
            if t.strip():
                st.audio(tts_bytes(t), format="audio/mp3")
            else:
                st.warning("Önce bir soru sor 😊")

    # 🆘 Yardım (SSS) altta, tıklayınca açılır
    with c_help:
        try:
            with st.popover("🆘", use_container_width=True):
                st.markdown("### Sıkça Sorulan Sorular")
                st.markdown("**1) Nasıl soru sorarım?**\n- Alttan yaz veya 🎤 kullan.")
                st.markdown("**2) PDF varsa ne olur?**\n- Metne göre adım adım anlatırım.")
                st.markdown("**3) Dinleme nasıl?**\n- 🔊 tuşuna bas.")
                st.markdown("**4) Yazmak zor gelirse?**\n- A/B/C seçebilirsin.")
        except Exception:
            with st.expander("🆘", expanded=False):
                st.markdown("### Sıkça Sorulan Sorular")
                st.markdown("**1) Nasıl soru sorarım?**\n- Alttan yaz veya 🎤 kullan.")
                st.markdown("**2) PDF varsa ne olur?**\n- Metne göre adım adım anlatırım.")
                st.markdown("**3) Dinleme nasıl?**\n- 🔊 tuşuna bas.")
                st.markdown("**4) Yazmak zor gelirse?**\n- A/B/C seçebilirsin.")

    # Chat input (en altta)
    soru = st.chat_input("Sorunu yaz")
    if soru:
        soruyu_isle(soru, pdf_text, extra_text)
