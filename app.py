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

# ------------------ OKUNABİLİRLİK CSS ------------------
st.markdown("""
<style>
html, body, [class*="css"] { font-size: 22px !important; }
p, li, div, span { line-height: 1.75 !important; }
.stChatMessage p { font-size: 22px !important; line-height: 1.75 !important; }
.stTextInput input, .stTextArea textarea { font-size: 22px !important; line-height: 1.75 !important; }
.stMarkdown { word-spacing: 0.10em !important; letter-spacing: 0.01em !important; }

/* Kart görünümü */
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:16px;
  padding:14px 16px;
  margin:10px 0;
  background: rgba(255,255,255,.6);
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

/* Butonlar */
.stButton button{ border-radius:14px !important; padding:10px 14px !important; }

/* Daha ferah */
.block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
</style>
""", unsafe_allow_html=True)

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
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=1000, cols=4)
    chat_sheet.append_row(["Kullanici", "Zaman", "Rol", "Mesaj"])

# ------------------ UTIL ------------------
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
                role = "user" if str(r.get("Rol","")).lower() == "user" else "assistant"
                content = r.get("Mesaj","")
                if content:
                    messages.append({"role": role, "content": content})
    except Exception as e:
        st.error(f"Sohbet geçmişi yüklenemedi: {e}")
    return messages

def kelime_istatistikleri(metinler):
    if not metinler: return "", ""
    text = " ".join(metinler).lower()
    tokens = re.findall(r"\w+", text, flags=re.UNICODE)
    stop = {"ve","veya","ile","ama","fakat","çünkü","ben","sen","o","biz","siz","onlar","bu","şu",
            "bir","iki","üç","mi","mı","mu","mü","de","da","ki","için","gibi","çok","az","ne","neden","nasıl","hangi"}
    words = [t for t in tokens if len(t)>2 and t not in stop]
    if not words: return "", ""
    counts = Counter(words)
    en_cok, _ = counts.most_common(1)[0]
    top5 = ", ".join([f"{w} ({c})" for w,c in counts.most_common(5)])
    return en_cok, top5

def oturum_ozeti_yaz():
    if "user" not in st.session_state or "start_time" not in st.session_state: return
    now_tr = datetime.now(ZoneInfo("Europe/Istanbul"))
    start = st.session_state.start_time
    dakika = round((now_tr-start).total_seconds()/60, 1)
    giris_str = start.strftime("%d.%m.%Y %H:%M:%S")
    cikis_str = now_tr.strftime("%d.%m.%Y %H:%M:%S")
    en_cok, diger = kelime_istatistikleri(st.session_state.get("user_texts", []))
    try:
        stats_sheet.append_row([st.session_state.user, giris_str, cikis_str, dakika, en_cok, diger])
    except Exception as e:
        st.error(f"Oturum özeti yazılırken hata: {e}")

# ------------------ TTS: noktalama/emoji temizle ------------------
def clean_for_tts(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)      # **kalın** temizle
    t = re.sub(r"[✅🧩🖼️💡❓🔊🆘🎤📚]", " ", t)  # emojiler
    t = re.sub(r"[#>\[\]\(\)\{\}_`~^=|\\/@]", " ", t)
    t = re.sub(r"[:;,.!?…“”\"'’\-–—]", " ", t)  # noktalama (TTS okumasın)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tts_bytes(text: str) -> bytes:
    safe = clean_for_tts(text)
    if len(safe) > 1200:
        safe = safe[:1200] + " ..."
    mp3_fp = BytesIO()
    gTTS(safe, lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

# ------------------ MODEL: JSON çıktısı zorunlu ------------------
def system_prompt_json():
    return """
Sen, özel öğrenme güçlüğü (Disleksi, Diskalkuli, Disgrafi) yaşayan ortaokul öğrencileri için okuma dostu yardımcı öğretmensin.

ÇIKTIYI SADECE JSON olarak ver. Başka hiçbir şey yazma.

Kurallar:
- Kısa cümle.
- Basit kelime.
- Her alan 1-2 cümle.
- emojis alanı 3 emoji olsun.
- ipucu1 ve ipucu2 kısa olsun.
- kisa_cevap tek cümle.
- kontrol_sorusu tek soru.

JSON ŞEMASI:
{
  "dikkat": "1 kısa merak uyandıran soru",
  "emojis": "3 emoji (örn: ⚙️🧩🔧)",
  "gorsel": "1 cümlelik benzetme (gerçek resim gerekmez)",
  "ipucu1": "kolay ipucu",
  "ipucu2": "örnek ipucu",
  "kisa_cevap": "en net kısa cevap",
  "kontrol_sorusu": "1 kontrol sorusu"
}
"""

def make_step_card(label, text):
    st.markdown(f"""
    <div class="card">
      <div class="badge">{label}</div>
      <div>{text}</div>
    </div>
    """, unsafe_allow_html=True)

def ask_model_steps(user_question: str, pdf_text: str, extra_text: str):
    content = ""
    if pdf_text:
        content += "PDF:\n" + pdf_text[:900] + "\n\n"
    if extra_text:
        content += "Metin:\n" + extra_text[:900] + "\n\n"
    prompt = (content + "Soru:\n" + user_question) if content else user_question

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":system_prompt_json()},
            {"role":"user","content":prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()

    # JSON parse güvenliği
    try:
        data = json.loads(raw)
    except:
        # model bazen JSON dışına taşarsa kurtarma
        m = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(m.group(0)) if m else {
            "dikkat": "Hazır mısın?",
            "emojis": "🙂📌✅",
            "gorsel": "Kısa bir örnekle düşünelim.",
            "ipucu1": "Kısa ipucu.",
            "ipucu2": "Kısa örnek.",
            "kisa_cevap": "Kısa cevap.",
            "kontrol_sorusu": "Anladın mı?"
        }
    return data

# ------------------ SORU İŞLE (adım adım) ------------------
def soruyu_isle(soru: str, pdf_text: str, extra_text: str):
    with st.chat_message("user"):
        st.write(soru)

    st.session_state.messages.append({"role":"user","content":soru})
    st.session_state.user_texts.append(soru)
    st.session_state.last_user_text = soru
    log_message(st.session_state.user, "user", soru)

    with st.chat_message("assistant"):
        try:
            steps = ask_model_steps(soru, pdf_text, extra_text)
            st.session_state.last_steps = steps
            st.session_state.reveal = 1  # 1: dikkat+görsel, 2: +ipucu1, 3:+ipucu2, 4:+cevap, 5:+kontrol

            # Ekrana sadece 1. adımı bas
            make_step_card("1) ❓ Dikkat", steps["dikkat"])
            make_step_card("2) 🖼️ Görsel", f'{steps["emojis"]} — {steps["gorsel"]}')

            # Ayrıca sohbet geçmişine "tek satır" değil, düzenli özet kaydı
            display_text = (
                f'❓ {steps["dikkat"]}\n'
                f'🖼️ {steps["emojis"]} {steps["gorsel"]}\n'
                f'💡 {steps["ipucu1"]}\n'
                f'💡 {steps["ipucu2"]}\n'
                f'✅ {steps["kisa_cevap"]}\n'
                f'🧩 {steps["kontrol_sorusu"]}'
            )
            st.session_state.messages.append({"role":"assistant","content":display_text})
            st.session_state.last_assistant_text = display_text
            log_message(st.session_state.user, "assistant", display_text)

        except Exception as e:
            st.error(f"Hata: {e}")

# ------------------ GİRİŞ ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.messages = load_history(st.session_state.user)
        st.session_state.user_texts = []
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.session_state.last_user_text = ""
        st.session_state.last_assistant_text = ""
        st.session_state.last_steps = None
        st.session_state.reveal = 0

        intro = (
            "✅ Ben kısa ve kolay anlatırım.\n"
            "• Önce **dikkat** + **görsel** ile başlarım.\n"
            "• Sonra **ipucu** veririm.\n"
            "• En sonda **kısa cevap** ve **kontrol sorusu** olur.\n"
            "• İstersen **🔊 Dinle** ile dinleyebilirsin.\n"
            "Hazırsan bir soru sor 😊"
        )
        if not st.session_state.messages:
            st.session_state.messages.append({"role":"assistant","content":intro})
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    top1, top2, top3 = st.columns([2,1,1])
    with top1:
        st.success(f"Hoş geldin ✍️ {st.session_state.user}")
    with top2:
        if st.button("🆘 Yardım", use_container_width=True):
            st.session_state.show_help = not st.session_state.get("show_help", False)
    with top3:
        if st.button("Çıkış Yap", use_container_width=True):
            oturum_ozeti_yaz()
            st.session_state.clear()
            st.rerun()

    if st.session_state.get("show_help", False):
        with st.expander("🆘 Yardım", expanded=True):
            st.markdown("- **Daha kolay anlat** yaz.\n- **Örnek ver** yaz.\n- **Adım adım** yaz.\n- **Tekrar et** yaz.\n- **🔊 Dinle** ile dinle.")

    # PDF / Metin (sade)
    with st.expander("📄 PDF / Metin (İstersen ekle)", expanded=False):
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

    # Sohbet geçmişi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # ADIM ADIM DEVAM BUTONLARI (tek akış)
    steps = st.session_state.get("last_steps")
    if steps:
        st.markdown("### 🔽 Adım adım devam")
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("💡 İpucu 1", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 2)
        with b2:
            if st.button("💡 İpucu 2", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 3)
        with b3:
            if st.button("✅ Kısa cevap", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 4)
        with b4:
            if st.button("🧩 Kontrol", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 5)

        # Gösterim (kartlarla ve boşluklu)
        if st.session_state.reveal >= 2:
            make_step_card("3) 💡 İpucu 1", steps["ipucu1"])
        if st.session_state.reveal >= 3:
            make_step_card("4) 💡 İpucu 2", steps["ipucu2"])
        if st.session_state.reveal >= 4:
            make_step_card("5) ✅ Kısa cevap", steps["kisa_cevap"])
        if st.session_state.reveal >= 5:
            make_step_card("6) 🧩 Kontrol", steps["kontrol_sorusu"])

    # Mikrofon (sabit)
    with st.expander("🎤 Sesle soru sor (tıkla–konuş–durdur)", expanded=False):
        audio_bytes = audio_recorder(
            text="Konuşmak için tıkla",
            pause_threshold=1.8,
            sample_rate=16000,
            key="mic_main",
        )
        if audio_bytes:
            last_len = st.session_state.get("last_audio_len", 0)
            if len(audio_bytes) != last_len:
                st.session_state["last_audio_len"] = len(audio_bytes)
                st.success("Ses alındı ✔️ Yazıya çevriliyor...")

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
                        mic_text = transcript.text

                    st.info(f"📝 Sesli soru: **{mic_text}**")
                    soruyu_isle(mic_text, pdf_text, extra_text)

                except Exception as e:
                    st.error(f"Ses yazıya çevrilirken hata oluştu: {e}")

    # Sesli dinle (temizlenmiş TTS)
    if st.button("🔊 Son cevabı dinle", use_container_width=True):
        t = st.session_state.get("last_assistant_text", "")
        if t.strip():
            try:
                audio_mp3 = tts_bytes(t)
                st.audio(audio_mp3, format="audio/mp3")
                st.caption("Noktalama/emoji temizlendi. Daha doğal okunur.")
            except Exception as e:
                st.error(f"Sesli okuma hatası: {e}")
        else:
            st.warning("Dinlenecek bir cevap yok.")

    # Yazıyla soru
    soru = st.chat_input("Sorunu yaz")
    if soru:
        soruyu_isle(soru, pdf_text, extra_text)
