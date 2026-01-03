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
#  OKUMA DOSTUM — ÖÖG + SUNUŞ YOLUYLA ÖĞRETİM (DERS SENARYOSU)
#  Öğretmen metin/PDF verir → öğrenci chatbotla okur → ana fikir/tema → sorular
#  Tasarım: sade, büyük punto, az buton, etiket yok.
# =========================================================

# ------------------ SAYFA AYARI ------------------
st.set_page_config(page_title="Okuma Dostum", layout="wide")
st.title("📚 Okuma Dostum")

# ------------------ ÖÖG DOSTU CSS ------------------
st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 22px !important; }
p, li, div, span { line-height: 1.85 !important; }
.stChatMessage p { font-size: 22px !important; line-height: 1.85 !important; }
.stTextInput input, .stTextArea textarea { font-size: 22px !important; line-height: 1.85 !important; }
.stMarkdown { word-spacing: 0.10em !important; letter-spacing: 0.01em !important; }

/* Kart */
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:18px;
  padding:14px 16px;
  margin:10px 0;
  background: rgba(255,255,255,.86);
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

/* Sade sayfa genişliği */
.block-container { padding-top: 1.1rem; padding-bottom: 2.2rem; max-width: 980px; }

/* Alt bar */
.bottombar { margin-top: 10px; margin-bottom: 6px; }
.stButton button{ border-radius:14px !important; padding:8px 12px !important; }
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


# ------------------ MODEL: SUNUŞ YOLUYLA + OKUDUĞUNU ANLAMA (ETİKETSİZ) ------------------
def system_prompt_json():
    return """
Sen, özel öğrenme güçlüğü olan (ÖÖG) ortaokul öğrencisi için derste kullanılan yardımcı öğretim materyalisisin.
Öğretim stratejin: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel).

DERS SENARYOSU:
Öğretmen bir METİN/PDF verir.
Öğrenci bu metni seninle okur.
Hedefler:
- Metni parça parça okumak ve anlamak
- Ana fikir / ana tema bulmak
- Metinden soruları cevaplamak
- Okuduğunu anlama becerisini güçlendirmek

KURALLAR:
- Öğrenciyi keşfe bırakma, rehberli ilerle.
- Uzun paragraf verme.
- Kısa cümle, basit kelime, madde madde.
- Etiket kullanma: “ön düzenleyici, görsel benzetme” gibi akademik başlık yazma.
- Başlıklar çocuk diliyle olsun.
- Yazma yükünü azalt: A/B/C seçmeli sorular üret.
- Metin varsa mutlaka metne dayan.

ÇIKTI: SADECE JSON. Başka hiçbir şey yazma.

JSON ŞEMASI:
{
  "acilis": "Bugün ne yapacağız? (1-2 cümle)",
  "parcalar": [
    {"metin":"kısa parça 1", "soru1":"Bu parçada kim/ne var?", "soru2":"Ne oldu?"},
    {"metin":"kısa parça 2", "soru1":"...", "soru2":"..."}
  ],
  "model": {
    "metin":"kısa örnek parça",
    "dusunce":["1 kısa adım","1 kısa adım","1 kısa adım"]
  },
  "ana_fikir": {
    "soru":"Bu metnin ana fikri hangisi?",
    "A":"...",
    "B":"...",
    "C":"...",
    "dogru":"A"
  },
  "metin_sorusu": {
    "soru":"Metne göre hangisi doğrudur?",
    "A":"...",
    "B":"...",
    "C":"...",
    "dogru":"B"
  },
  "kisa_tekrar": "1 cümle özet",
  "kontrol": "1 kısa kontrol sorusu (Evet/Hayır ya da A/B)",
  "geribildirim": {
    "dogru":"1 cümle",
    "yanlis":"1 cümle"
  }
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


def ask_model(user_question: str, source_text: str) -> dict:
    prompt = (
        f"SORU / HEDEF: {user_question}\n\n"
        f"KAYNAK METİN:\n{source_text}\n\n"
        "Not: Metni parça parça ver. Sorular kısa olsun."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_json()},
            {"role": "user", "content": prompt},
        ],
    )

    d = safe_json_load(resp.choices[0].message.content)

    # Eksikleri doldur
    d.setdefault("acilis", "Bugün metinden ana fikri bulacağız.")
    d.setdefault("parcalar", [])
    d.setdefault("model", {"metin": "", "dusunce": []})
    d.setdefault("ana_fikir", {"soru": "", "A": "", "B": "", "C": "", "dogru": "A"})
    d.setdefault("metin_sorusu", {"soru": "", "A": "", "B": "", "C": "", "dogru": "A"})
    d.setdefault("kisa_tekrar", "Kısaca: Ana fikir metnin en önemli mesajıdır.")
    d.setdefault("kontrol", "Ana fikir tek cümle olur mu? (Evet/Hayır)")
    d.setdefault("geribildirim", {"dogru": "Harika! Doğru seçtin.", "yanlis": "Sorun değil. Metnin tamamını kapsayanı seç."})

    # Parça sayısını sınırla (ekranı yormasın)
    if isinstance(d.get("parcalar"), list):
        d["parcalar"] = d["parcalar"][:4]
    else:
        d["parcalar"] = []

    return d


# ------------------ UI HELPERS ------------------
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
    # Kayda gitsin diye sade metin
    out = []
    out.append(d.get("acilis", ""))

    for i, p in enumerate(d.get("parcalar", []), start=1):
        out.append(f"Parça {i}: {p.get('metin','')}")
        out.append(f"- {p.get('soru1','')}")
        out.append(f"- {p.get('soru2','')}")

    m = d.get("model", {})
    if m.get("metin"):
        out.append("Örnek:")
        out.append(m.get("metin", ""))
        for step in (m.get("dusunce") or [])[:3]:
            out.append(f"- {step}")

    af = d.get("ana_fikir", {})
    out.append(af.get("soru", ""))
    out.append(f"A) {af.get('A','')}")
    out.append(f"B) {af.get('B','')}")
    out.append(f"C) {af.get('C','')}")

    ms = d.get("metin_sorusu", {})
    out.append(ms.get("soru", ""))
    out.append(f"A) {ms.get('A','')}")
    out.append(f"B) {ms.get('B','')}")
    out.append(f"C) {ms.get('C','')}")

    out.append(d.get("kisa_tekrar", ""))
    out.append(d.get("kontrol", ""))

    return "\n".join([x for x in out if x])


def show_step(d: dict, step: int):
    # step 1: açılış + parça 1
    # step 2..: diğer parçalar
    # model
    # ana fikir
    # metin sorusu
    # tekrar + kontrol

    parcalar = d.get("parcalar", [])

    if step == 1:
        make_card("Hadi başlayalım", d.get("acilis", ""))
        if parcalar:
            p = parcalar[0]
            make_card(
                "Oku",
                f"{p.get('metin','')}<br><br>• {p.get('soru1','')}<br>• {p.get('soru2','')}",
            )
        return

    # parçalar 2-4
    if 2 <= step <= 4:
        idx = step - 1
        if idx < len(parcalar):
            p = parcalar[idx]
            make_card(
                "Oku",
                f"{p.get('metin','')}<br><br>• {p.get('soru1','')}<br>• {p.get('soru2','')}",
            )
        else:
            make_card("Devam", "Bir sonraki adıma geçelim.")
        return

    # model
    if step == 5:
        m = d.get("model", {})
        metin = m.get("metin", "")
        steps = (m.get("dusunce") or [])[:3]
        body = metin if metin else "Kısa bir örnek düşünelim."
        if steps:
            body += "<br><br>" + "<br>".join([f"• {s}" for s in steps])
        make_card("Ben bir örnek yapayım", body)
        return

    # ana fikir sorusu
    if step == 6:
        af = d.get("ana_fikir", {})
        body = (
            f"<b>{af.get('soru','')}</b><br><br>"
            f"A) {af.get('A','')}<br>"
            f"B) {af.get('B','')}<br>"
            f"C) {af.get('C','')}"
        )
        make_card("Şimdi sen seç", body)
        return

    # metin sorusu
    if step == 7:
        ms = d.get("metin_sorusu", {})
        body = (
            f"<b>{ms.get('soru','')}</b><br><br>"
            f"A) {ms.get('A','')}<br>"
            f"B) {ms.get('B','')}<br>"
            f"C) {ms.get('C','')}"
        )
        make_card("Bir soru daha", body)
        return

    # tekrar + kontrol
    if step == 8:
        make_card("Kısaca", d.get("kisa_tekrar", ""))
        make_card("Kontrol", d.get("kontrol", ""))
        return


def build_source_text(pdf_text: str, extra_text: str) -> str:
    # Öğretmen metin vermediyse, yine de çalışsın ama kısa uyarı versin
    src = ""
    if pdf_text.strip():
        src += pdf_text.strip() + "\n"
    if extra_text.strip():
        src += extra_text.strip() + "\n"
    src = src.strip()
    return src


# ------------------ DERS BAŞLAT / GÜNCELLE ------------------
def start_lesson(lesson_goal: str, pdf_text: str, extra_text: str):
    source_text = build_source_text(pdf_text, extra_text)

    if not source_text:
        # Metin yoksa bile model çalışsın, ama hedefi "konu anlatımı" gibi kur
        source_text = "Metin yok. Konuyu kısa bir metin gibi anlat ve ana fikir çalışması yaptır."

    # kullanıcı mesajı
    with st.chat_message("user"):
        st.write(lesson_goal)

    st.session_state.messages.append({"role": "user", "content": lesson_goal})
    st.session_state.user_texts.append(lesson_goal)
    log_message(st.session_state.user, "user", lesson_goal)

    # asistan üretimi
    with st.chat_message("assistant"):
        d = ask_model(lesson_goal, source_text)
        st.session_state.last_lesson = d
        st.session_state.step = 1

        # ilk ekran: açılış + parça 1
        show_step(d, 1)

        # history/sheet kaydı
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

        st.session_state.last_assistant_text = ""
        st.session_state.last_audio_len = 0
        st.session_state.last_lesson = None
        st.session_state.step = 0

        if not st.session_state.messages:
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "✅ **Nasıl kullanılır?**\n"
                    "- Öğretmen metni (PDF) yükler veya yapıştırır.\n"
                    "- Sen metni benimle okursun.\n"
                    "- Sonra ana fikri buluruz ve soruları çözeriz.\n"
                    "- 🎤 ile sesle sorabilirsin. 🔊 ile dinleyebilirsin.\n"
                    "- 🆘 ile yardım açılır.\n"
                )
            })

        st.rerun()


# ------------------ ANA EKRAN ------------------
else:
    # Üst bar
    top1, top2 = st.columns([3, 1])
    with top1:
        st.success(f"Hoş geldin 🌈 {st.session_state.user}")
    with top2:
        if st.button("Çıkış", use_container_width=True):
            oturum_ozeti_yaz()
            st.session_state.clear()
            st.rerun()

    # Öğretmen: metni yükler/yapıştırır
    with st.expander("📄 Öğretmen: Metni ekle (PDF / Yapıştır)", expanded=False):
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
            extra_text = st.text_area("Metni buraya yapıştır", height=170)

    pdf_text = locals().get("pdf_text", "")
    extra_text = locals().get("extra_text", "")

    # Sohbet geçmişi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # Ders adımları (tek tuşla daha sade: DEVAM)
    d = st.session_state.get("last_lesson")
    if d and st.session_state.step > 0:
        st.markdown("### ✅ Ders")
        show_step(d, st.session_state.step)

        # A/B/C etkileşimleri sadece ilgili adımda
        if st.session_state.step == 6:
            af = d.get("ana_fikir", {})
            choice = st.radio("Seç:", ["A", "B", "C"], horizontal=True, index=0, key="choice_af")
            if st.button("Kontrol et", use_container_width=True):
                if choice == af.get("dogru", "A"):
                    make_card("✅", d.get("geribildirim", {}).get("dogru", "Harika!"))
                else:
                    make_card("🟡", d.get("geribildirim", {}).get("yanlis", "Sorun değil."))

        if st.session_state.step == 7:
            ms = d.get("metin_sorusu", {})
            choice2 = st.radio("Seç:", ["A", "B", "C"], horizontal=True, index=0, key="choice_ms")
            if st.button("Kontrol et", use_container_width=True):
                if choice2 == ms.get("dogru", "A"):
                    make_card("✅", d.get("geribildirim", {}).get("dogru", "Harika!"))
                else:
                    make_card("🟡", d.get("geribildirim", {}).get("yanlis", "Sorun değil."))

        # Tek buton: Devam
        col_next, col_restart = st.columns([2, 1])
        with col_next:
            if st.button("➡️ Devam", use_container_width=True):
                st.session_state.step = min(st.session_state.step + 1, 8)
                st.rerun()
        with col_restart:
            if st.button("🔄 Baştan", use_container_width=True):
                st.session_state.step = 1
                st.rerun()

    # ------------------ ALT BAR: 🎤 + 🔊 + 🆘 (CHAT YANINDA) ------------------
    st.markdown('<div class="bottombar"></div>', unsafe_allow_html=True)
    c_mic, c_listen, c_help = st.columns([1, 1, 1])

    # 🎤 Mikrofon: küçük emoji buton (popover varsa)
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

                        # Sesle gelen metin: ders hedefi gibi başlat
                        start_lesson(mic_text, pdf_text, extra_text)
        except Exception:
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
                        start_lesson(mic_text, pdf_text, extra_text)

    # 🔊 Dinle
    with c_listen:
        if st.button("🔊", use_container_width=True):
            t = st.session_state.get("last_assistant_text", "")
            if t.strip():
                st.audio(tts_bytes(t), format="audio/mp3")
            else:
                st.warning("Önce bir ders başlatalım 😊")

    # 🆘 Yardım (SSS) altta, tıklayınca açılır
    with c_help:
        try:
            with st.popover("🆘", use_container_width=True):
                st.markdown("### Sıkça Sorulan Sorular")
                st.markdown("**1) Ne yapacağız?**\n- Metni birlikte okuyup ana fikri bulacağız.")
                st.markdown("**2) Yazmak zor gelirse?**\n- A/B/C ile seçebilirsin.")
                st.markdown("**3) PDF yoksa?**\n- Yine çalışır ama öğretmen metin eklerse daha iyi olur.")
                st.markdown("**4) Dinlemek?**\n- 🔊 tuşuna bas.")
        except Exception:
            with st.expander("🆘", expanded=False):
                st.markdown("### Sıkça Sorulan Sorular")
                st.markdown("**1) Ne yapacağız?**\n- Metni birlikte okuyup ana fikri bulacağız.")
                st.markdown("**2) Yazmak zor gelirse?**\n- A/B/C ile seçebilirsin.")
                st.markdown("**3) PDF yoksa?**\n- Yine çalışır ama öğretmen metin eklerse daha iyi olur.")
                st.markdown("**4) Dinlemek?**\n- 🔊 tuşuna bas.")

    # ------------------ CHAT INPUT (EN ALT) ------------------
    # Öğrenci buraya hedef yazabilir: “Ana fikri bulalım” / “Bu metni anlat” gibi
    soru = st.chat_input("Sorunu yaz (ör: Bu metnin ana fikrini bulalım)")
    if soru:
        start_lesson(soru, pdf_text, extra_text)

