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
st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 22px !important; }
p, li, div, span { line-height: 1.75 !important; }
.stChatMessage p { font-size: 22px !important; line-height: 1.75 !important; }
.stTextInput input, .stTextArea textarea { font-size: 22px !important; line-height: 1.75 !important; }
.stMarkdown { word-spacing: 0.10em !important; letter-spacing: 0.01em !important; }

.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:16px;
  padding:14px 16px;
  margin:10px 0;
  background: rgba(255,255,255,.75);
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
.stButton button{ border-radius:14px !important; padding:10px 14px !important; }
.block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
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
        "ve", "veya", "ile", "ama", "fakat", "çünkü",
        "ben", "sen", "o", "biz", "siz", "onlar",
        "bu", "şu", "bir", "iki", "üç",
        "mi", "mı", "mu", "mü",
        "de", "da", "ki",
        "için", "gibi", "çok", "az",
        "ne", "neden", "nasıl", "hangi",
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

# ------------------ TTS: TEMİZ OKUMA ------------------
def clean_for_tts(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"[✅🧩🖼️💡❓🔊🆘🎤📚]", " ", t)
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

# ------------------ SUNUŞ YOLUYLA ÖĞRETİM: JSON ŞEMA ------------------
def system_prompt_json():
    return """
Sen, özel öğrenme güçlüğü (Disleksi, Diskalkuli, Disgrafi) yaşayan ortaokul öğrencisiyle derste kullanılan yardımcı öğretim chatbotusun.
ÖĞRETMEN derste seni yardımcı materyal olarak kullanır. Sen öğretmenin yerini almazsın.
ÖĞRETİM STRATEJİN: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel). Öğrenciyi keşfe bırakma.

ÇIKTIYI SADECE JSON olarak ver. Başka hiçbir şey yazma.

DİL ve BİÇİM:
- 5-6. sınıf düzeyi.
- Kısa cümle.
- Basit kelime.
- Her alan 1-2 cümle.
- "tanim_maddeler" 3-5 kısa madde olsun.
- "model_adimlar" 2-3 adım olsun.
- "rehberli_soru" mutlaka A/B/C seçenekli olsun.
- "kisa_tekrar" tek cümle.
- "kontrol" tek soru.
- "geri_bildirim_dogru" ve "geri_bildirim_yanlis" tek cümle.

JSON ŞEMASI:
{
  "on_duzenleyici": "Bugün ne öğreneceğiz? (1-2 cümle, dikkat çekici)",
  "gorsel_benzetme": "1 cümlelik benzetme (gerçek resim gerekmiyor)",
  "tanim_maddeler": ["madde1","madde2","madde3"],
  "model_adimlar": ["adım1","adım2"],
  "rehberli_soru": {
    "soru": "A/B/C seçmeli kısa soru",
    "A": "seçenek A",
    "B": "seçenek B",
    "C": "seçenek C",
    "dogru": "A veya B veya C"
  },
  "kisa_tekrar": "1 cümle özet",
  "kontrol": "1 kısa kontrol sorusu",
  "geri_bildirim_dogru": "Doğru için 1 cümle",
  "geri_bildirim_yanlis": "Yanlış için 1 cümle"
}
"""

def make_card(title, body):
    st.markdown(
        f"""
<div class="card">
  <div class="badge">{title}</div>
  <div>{body}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def safe_json_load(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            return json.loads(m.group(0))
        return {}

def ask_model(teacher_mode: str, user_question: str, pdf_text: str, extra_text: str) -> dict:
    content = ""
    if teacher_mode == "Metinden Öğretim":
        if pdf_text:
            content += "PDF:\n" + pdf_text[:900] + "\n\n"
        if extra_text:
            content += "Metin:\n" + extra_text[:900] + "\n\n"
        if not content:
            content = "Not: Metin yok. Konu anlatımı gibi ilerle.\n\n"

    prompt = f"MOD: {teacher_mode}\nSoru/Konu: {user_question}\n\n{content}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_json()},
            {"role": "user", "content": prompt},
        ],
    )
    data = safe_json_load(resp.choices[0].message.content)

    # eksik anahtarları garantiye al
    data.setdefault("on_duzenleyici", "")
    data.setdefault("gorsel_benzetme", "")
    data.setdefault("tanim_maddeler", [])
    data.setdefault("model_adimlar", [])
    data.setdefault("rehberli_soru", {"soru":"", "A":"", "B":"", "C":"", "dogru":"A"})
    data.setdefault("kisa_tekrar", "")
    data.setdefault("kontrol", "")
    data.setdefault("geri_bildirim_dogru", "")
    data.setdefault("geri_bildirim_yanlis", "")
    return data

def format_for_history(d: dict) -> str:
    maddeler = "\n".join([f"• {x}" for x in (d.get("tanim_maddeler") or [])])
    model = "\n".join([f"{i+1}) {x}" for i, x in enumerate(d.get("model_adimlar") or [])])
    rs = d.get("rehberli_soru") or {}
    rehber = (
        f"{rs.get('soru','')}\n"
        f"A) {rs.get('A','')}\n"
        f"B) {rs.get('B','')}\n"
        f"C) {rs.get('C','')}\n"
        f"(Doğru: {rs.get('dogru','')})"
    )
    return (
        f"🧠 Ön düzenleyici: {d.get('on_duzenleyici','')}\n"
        f"🖼️ Görsel: {d.get('gorsel_benzetme','')}\n"
        f"📌 Tanım/Kural:\n{maddeler}\n"
        f"👣 Model (ben yapıyorum):\n{model}\n"
        f"🎯 Rehberli uygulama:\n{rehber}\n"
        f"🔁 Kısa tekrar: {d.get('kisa_tekrar','')}\n"
        f"✅ Kontrol: {d.get('kontrol','')}\n"
    )

def show_steps(d: dict, reveal: int):
    # reveal:
    # 1: ön düzenleyici + görsel
    # 2: + tanım
    # 3: + model
    # 4: + rehberli soru
    # 5: + kısa tekrar + kontrol
    if reveal >= 1:
        make_card("1) 🧠 Ön düzenleyici", d.get("on_duzenleyici",""))
        make_card("2) 🖼️ Görsel / benzetme", d.get("gorsel_benzetme",""))

    if reveal >= 2:
        maddeler = d.get("tanim_maddeler") or []
        body = "<br>".join([f"• <b>{m}</b>" if i == 0 else f"• {m}" for i, m in enumerate(maddeler)])
        make_card("3) 📌 Tanım / Kural", body if body else "• (Boş)")

    if reveal >= 3:
        adimlar = d.get("model_adimlar") or []
        body = "<br>".join([f"{i+1}) {a}" for i, a in enumerate(adimlar)])
        make_card("4) 👣 Model (Ben yapıyorum)", body if body else "1) (Boş)")

    if reveal >= 4:
        rs = d.get("rehberli_soru") or {}
        body = (
            f"<b>{rs.get('soru','')}</b><br><br>"
            f"A) {rs.get('A','')}<br>"
            f"B) {rs.get('B','')}<br>"
            f"C) {rs.get('C','')}"
        )
        make_card("5) 🎯 Rehberli uygulama (A/B/C)", body)

    if reveal >= 5:
        make_card("6) 🔁 Kısa tekrar", d.get("kisa_tekrar",""))
        make_card("7) ✅ Kontrol", d.get("kontrol",""))

# ------------------ SORU İŞLE (SUNUŞ AKIŞI) ------------------
def soruyu_isle(teacher_mode: str, soru: str, pdf_text: str, extra_text: str):
    with st.chat_message("user"):
        st.write(soru)

    st.session_state.messages.append({"role": "user", "content": soru})
    st.session_state.user_texts.append(soru)
    st.session_state.last_user_text = soru

    log_message(st.session_state.user, "user", soru)

    with st.chat_message("assistant"):
        try:
            d = ask_model(teacher_mode, soru, pdf_text, extra_text)
            st.session_state.last_lesson = d
            st.session_state.reveal = 1
            st.session_state.last_assistant_text = format_for_history(d)

            # ilk etapta sadece 1-2 adım
            show_steps(d, reveal=1)

            # history + sheets için kaydet
            st.session_state.messages.append({"role": "assistant", "content": st.session_state.last_assistant_text})
            log_message(st.session_state.user, "assistant", st.session_state.last_assistant_text)

        except Exception as e:
            st.error(f"Hata: {e}")

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
        st.session_state.show_help = False
        st.session_state.teacher_mode = "Konu Anlatımı"

        if not st.session_state.messages:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "✅ Ben derste yardımcı materyalim.\n"
                        "Sunuş yoluyla öğretim yaparım:\n"
                        "1) Ön düzenleyici\n2) Tanım\n3) Model\n4) Rehberli uygulama (A/B/C)\n5) Tekrar + kontrol\n"
                        "Hazırsan bir konu yaz 😊"
                    ),
                }
            )
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    top1, top2, top3 = st.columns([2, 1, 1])
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

    # ✅ NASIL KULLANILIR
    st.info(
        "✅ **Nasıl kullanılır?**\n\n"
        "1) Üstten **Öğretmen Modu** seç.\n"
        "2) Alttan **Sorunu yaz** ya da **🎤 Mikrofon** ile sor.\n"
        "3) Ben **sunuş yoluyla** anlatırım: Ön düzenleyici → Tanım → Model → A/B/C → Tekrar → Kontrol.\n"
        "4) Dinlemek için **🔊 Son dersi dinle**.\n",
        icon="ℹ️",
    )

    # Öğretmen modu
    st.session_state.teacher_mode = st.selectbox(
        "👩‍🏫 Öğretmen Modu",
        ["Konu Anlatımı", "Metinden Öğretim", "Kısa Değerlendirme"],
        index=["Konu Anlatımı", "Metinden Öğretim", "Kısa Değerlendirme"].index(st.session_state.teacher_mode),
    )

    # PDF / Metin
    with st.expander("📄 PDF / Metin (Metinden Öğretim için)", expanded=False):
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

    # Yardım (SSS)
    if st.session_state.get("show_help", False):
        with st.expander("🆘 Yardım (SSS)", expanded=True):
            with st.expander("1) Bu chatbot ne işe yarar?", expanded=False):
                st.write("Derste **yardımcı materyal** olarak kullanılır. **Sunuş yoluyla** anlatır, örnek gösterir ve A/B/C ile çalıştırır.")
            with st.expander("2) Öğretmen Modu ne?", expanded=False):
                st.write("Konu Anlatımı: Konuyu anlatır. Metinden Öğretim: PDF/metinden öğretir. Kısa Değerlendirme: Hızlı A/B/C soruları üretir.")
            with st.expander("3) Sesle soru sorabilir miyim?", expanded=False):
                st.write("Evet. Aşağıdaki **🎤 Mikrofon** ile sorabilirsin.")
            with st.expander("4) Cevabı nasıl dinlerim?", expanded=False):
                st.write("**🔊 Son dersi dinle** butonuna bas.")

    # Sohbet geçmişi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # ADIM ADIM DEVAM
    d = st.session_state.get("last_lesson")
    if d:
        st.markdown("### 🔽 Ders akışını adım adım göster")
        b1, b2, b3, b4, b5 = st.columns(5)
        with b1:
            if st.button("1-2", use_container_width=True):
                st.session_state.reveal = 1
        with b2:
            if st.button("+ Tanım", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 2)
        with b3:
            if st.button("+ Model", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 3)
        with b4:
            if st.button("+ A/B/C", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 4)
        with b5:
            if st.button("+ Tekrar/Kontrol", use_container_width=True):
                st.session_state.reveal = max(st.session_state.reveal, 5)

        show_steps(d, st.session_state.reveal)

        # A/B/C şıklı etkileşim (rehberli uygulama)
        if st.session_state.reveal >= 4:
            rs = d.get("rehberli_soru") or {}
            choice = st.radio("Seçimini yap:", ["A", "B", "C"], horizontal=True, index=0, key="abctest")
            if st.button("Cevabı Kontrol Et", use_container_width=True):
                if choice == rs.get("dogru"):
                    make_card("✅ Geri bildirim", d.get("geri_bildirim_dogru", "Aferin!"))
                else:
                    make_card("🟡 Geri bildirim", d.get("geri_bildirim_yanlis", "Sorun değil. Bir daha bakalım."))

    # 🎤 Mikrofon (her zaman görünür)
    st.markdown("### 🎤 Sesle soru sor")
    with st.container(border=True):
        st.caption("Tıkla → konuş → durdur. Ben yazıya çeviririm.")
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
                    soruyu_isle(st.session_state.teacher_mode, mic_text, pdf_text, extra_text)

                except Exception as e:
                    st.error(f"Ses yazıya çevrilirken hata oluştu: {e}")

    # 🔊 Son dersi dinle
    if st.button("🔊 Son dersi dinle", use_container_width=True):
        t = st.session_state.get("last_assistant_text", "")
        if t.strip():
            try:
                st.audio(tts_bytes(t), format="audio/mp3")
                st.caption("Noktalama/emoji temizlendi. Daha doğal okunur.")
            except Exception as e:
                st.error(f"Sesli okuma hatası: {e}")
        else:
            st.warning("Dinlenecek bir ders yok.")

    # Yazıyla soru
    soru = st.chat_input("Sorunu yaz (ör: Hücre zarı nedir?)")
    if soru:
        soruyu_isle(st.session_state.teacher_mode, soru, pdf_text, extra_text)
