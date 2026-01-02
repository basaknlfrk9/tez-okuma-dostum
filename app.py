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

# ------------------ SAYFA AYARI ------------------
st.set_page_config(page_title="Okuma Dostum", layout="wide")
st.title("📚 Okuma Dostum")

# ------------------ OKUNABİLİRLİK CSS ------------------
st.markdown(
    """
    <style>
      html, body, [class*="css"]  { font-size: 18px !important; }
      .stChatMessage { line-height: 1.6 !important; }
      .stMarkdown, .stText { line-height: 1.6 !important; }
      .okuma-card {
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid rgba(0,0,0,0.10);
        margin-bottom: 10px;
      }
      .okuma-title { font-weight: 700; font-size: 18px; margin-bottom: 8px; }
      .okuma-item { margin: 6px 0; }
      .okuma-small { opacity: 0.75; font-size: 14px; }
      .okuma-btn { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------ OPENAI CLIENT ------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ GOOGLE SHEETS BAĞLANTISI ------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_info(
    st.secrets["GSHEETS"],
    scopes=scope,
)

gc = gspread.authorize(credentials)
workbook = gc.open_by_url(st.secrets["GSHEET_URL"])

stats_sheet = workbook.sheet1

try:
    chat_sheet = workbook.worksheet("Sohbet")
except WorksheetNotFound:
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=1000, cols=4)
    chat_sheet.append_row(["Kullanici", "Zaman", "Rol", "Mesaj"])


# ------------------ KELİME İSTATİSTİĞİ ------------------
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
    en_cok_kelime, _ = counts.most_common(1)[0]
    top5 = counts.most_common(5)
    diger = ", ".join([f"{w} ({c})" for w, c in top5])

    return en_cok_kelime, diger


# ------------------ SOHBETİ SHEET'E YAZ / YÜKLE ------------------
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
                rol_raw = str(r.get("Rol", "")).lower()
                role = "user" if rol_raw == "user" else "assistant"
                content = r.get("Mesaj", "")
                if content:
                    messages.append({"role": role, "content": content})
    except Exception as e:
        st.error(f"Sohbet geçmişi yüklenemedi: {e}")
    return messages


# ------------------ OTURUM ÖZETİ YAZ ------------------
def oturum_ozeti_yaz():
    if "user" not in st.session_state:
        return
    if "start_time" not in st.session_state:
        return

    now_tr = datetime.now(ZoneInfo("Europe/Istanbul"))
    start = st.session_state.start_time

    dakika = round((now_tr - start).total_seconds() / 60, 1)
    giris_str = start.strftime("%d.%m.%Y %H:%M:%S")
    cikis_str = now_tr.strftime("%d.%m.%Y %H:%M:%S")

    user_texts = st.session_state.get("user_texts", [])
    en_cok, diger = kelime_istatistikleri(user_texts)

    try:
        stats_sheet.append_row(
            [st.session_state.user, giris_str, cikis_str, dakika, en_cok, diger]
        )
    except Exception as e:
        st.error(f"Oturum özeti yazılırken hata: {e}")


# ------------------ TTS (gTTS) ------------------
def tts_bytes(text: str) -> bytes:
    # Çok uzun metin TTS'te sorun çıkarabiliyor; güvenli kırp.
    safe = text.strip()
    if len(safe) > 1200:
        safe = safe[:1200] + " ..."
    mp3_fp = BytesIO()
    tts = gTTS(safe, lang="tr")
    tts.write_to_fp(mp3_fp)
    return mp3_fp.getvalue()


# ------------------ PROMPT ŞABLONU ------------------
def build_system_prompt():
    return (
        "Sen, özel öğrenme güçlüğü (Disleksi, Diskalkuli, Disgrafi) yaşayan ortaokul "
        "öğrencileri için okuma dostu bir yardımcı öğretmensin.\n\n"
        "ZORUNLU YAZIM KURALLARI:\n"
        "- Paragraf yok. Sadece MADDE MADDE yaz.\n"
        "- Kısa cümle: 1 cümlede 1 fikir.\n"
        "- En fazla 7 madde.\n"
        "- Zor kelime varsa parantez içinde kısaca açıkla.\n"
        "- Anahtar kelimeleri **kalın** yaz.\n\n"
        "ZORUNLU CEVAP AKIŞI (her soruda sırayla):\n"
        "1) ❓ Merak (1 soru)\n"
        "2) 🖼️ Görsel (1 cümlelik benzetme, gerçek görsel gerekmez)\n"
        "3) 💡 İpucu 1 (kolay)\n"
        "4) 💡 İpucu 2 (örnek)\n"
        "5) ✅ Kısa cevap\n"
        "6) 🧩 Kontrol (1 soru)\n"
        "7) 🔊 Dinle ister misin? (Evet/Hayır)  |  🆘 Yardım ister misin? (Evet/Hayır)\n\n"
        "ÖĞRENCİYE UYGUNLUK:\n"
        "- Disleksi: kısa, net, madde, adım adım.\n"
        "- Disgrafi: uzun yazı isteme; seçenek sun (A/B/C).\n"
        "- Diskalkuli: işlem varsa adım adım örnekle.\n"
    )


# ------------------ SORU CEVAPLAMA ------------------
def soruyu_isle(soru: str, pdf_text: str, extra_text: str):
    with st.chat_message("user"):
        st.write(soru)

    st.session_state.messages.append({"role": "user", "content": soru})
    st.session_state.user_texts.append(soru)
    st.session_state.last_user_text = soru

    if "user" in st.session_state:
        log_message(st.session_state.user, "user", soru)

    icerik = ""
    if pdf_text:
        icerik += "PDF metni:\n" + pdf_text[:900] + "\n\n"
    if extra_text:
        icerik += "Ek metin:\n" + extra_text[:900] + "\n\n"

    tam_soru = (icerik + "Öğrencinin sorusu:\n" + soru) if icerik else soru

    system_prompt = build_system_prompt()

    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": tam_soru},
                ],
            )
            cevap = response.choices[0].message.content
            st.write(cevap)

            st.session_state.messages.append({"role": "assistant", "content": cevap})
            st.session_state.last_assistant_text = cevap  # 🔊 dinlemek için

            if "user" in st.session_state:
                log_message(st.session_state.user, "assistant", cevap)

        except Exception as e:
            st.error(f"Hata: {e}")


# ------------------ GİRİŞ EKRANI ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        isim = isim.strip()
        st.session_state.user = isim
        st.session_state.messages = load_history(isim)

        st.session_state.user_texts = []
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.session_state.process_mode = None
        st.session_state.last_audio_len = 0
        st.session_state.last_user_text = ""
        st.session_state.last_assistant_text = ""

        # İlk yönerge (tek ekran, yardım, dinle)
        intro = (
            "✅ Ben kısa ve kolay anlatırım.\n\n"
            "• Sorunu **yazarak** sorabilirsin.\n"
            "• İstersen **🎤 sesle** sorabilirsin.\n"
            "• İstersen **🔊 Dinle** ile dinleyebilirsin.\n"
            "• Takılırsan **🆘 Yardım** butonuna bas.\n\n"
            "Hazırsan bir soru sor 😊"
        )
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": intro})
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    # Eksik state'leri tamamla
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("user_texts", [])
    st.session_state.setdefault("start_time", datetime.now(ZoneInfo("Europe/Istanbul")))
    st.session_state.setdefault("process_mode", None)
    st.session_state.setdefault("last_audio_len", 0)
    st.session_state.setdefault("last_user_text", "")
    st.session_state.setdefault("last_assistant_text", "")

    # ÜST BAR: Çıkış + Yardım
    top_c1, top_c2, top_c3 = st.columns([2, 1, 1])
    with top_c1:
        st.success(f"Hoş geldin 🌈 {st.session_state.user}")
    with top_c2:
        if st.button("🆘 Yardım", use_container_width=True):
            st.session_state.show_help = True
    with top_c3:
        if st.button("Çıkış Yap", use_container_width=True):
            oturum_ozeti_yaz()
            st.session_state.clear()
            st.rerun()

    if st.session_state.get("show_help"):
        with st.expander("🆘 Yardım Menüsü", expanded=True):
            st.markdown(
                """
                - “**Daha kolay anlat**” yazabilirsin.  
                - “**Örnek ver**” yazabilirsin.  
                - “**Adım adım** anlat” yazabilirsin.  
                - “**Tekrar et**” yazabilirsin.  
                - **🔊 Dinle** ile dinleyebilirsin.
                """
            )

    # TEK ALAN: PDF / Metin (sidebar yok)
    with st.expander("📄 PDF / Metin (İstersen ekle)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**PDF yükle**")
            pdf_text = ""
            pdf_file = st.file_uploader("PDF seç", type="pdf")
            if pdf_file is not None:
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        pdf_text += txt + "\n"
        with c2:
            st.markdown("**Metin yapıştır**")
            extra_text = st.text_area("Metni buraya yapıştır", height=180)

    # pdf_text / extra_text expander dışında da lazım
    pdf_text = locals().get("pdf_text", "")
    extra_text = locals().get("extra_text", "")

    # TEK BUTON ŞERİDİ: Basitleştir / Maddele
    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button("🅰️ Metni basitleştir", use_container_width=True):
            if not (pdf_text or extra_text or st.session_state.last_user_text):
                st.warning("Önce PDF, metin ya da bir soru olmalı 😊")
            else:
                st.session_state.process_mode = "basit"
    with b2:
        if st.button("🧩 Madde madde açıkla", use_container_width=True):
            if not (pdf_text or extra_text or st.session_state.last_user_text):
                st.warning("Önce PDF, metin ya da bir soru olmalı 😊")
            else:
                st.session_state.process_mode = "madde"
    with b3:
        st.caption("İpucu: Metin uzun gelirse “daha kolay anlat” yaz.")

    # SOHBET GEÇMİŞİ
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # METNİ İŞLEME ÇIKTISI
    if st.session_state.get("process_mode") in ("basit", "madde") and (
        pdf_text or extra_text or st.session_state.last_user_text
    ):
        parcalar = []
        if pdf_text:
            parcalar.append(pdf_text)
        if extra_text:
            parcalar.append(extra_text)
        if st.session_state.last_user_text:
            parcalar.append(st.session_state.last_user_text)

        kaynak_metin = "\n".join(parcalar).strip()

        with st.chat_message("assistant"):
            if st.session_state.process_mode == "basit":
                st.markdown("### 🅰️ Basitleştirilmiş Hali")
                system_prompt = build_system_prompt()
                user_content = (
                    "Aşağıdaki metni **okuma güçlüğü olan** ortaokul öğrencisine göre "
                    "**kısa cümlelerle ve madde madde** anlat:\n\n" + kaynak_metin
                )
            else:
                st.markdown("### 🧩 Madde Madde")
                system_prompt = build_system_prompt()
                user_content = (
                    "Aşağıdaki metnin en önemli noktalarını **kısa maddelerle** çıkar:\n\n"
                    + kaynak_metin
                )

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                )
                cevap = response.choices[0].message.content
                st.write(cevap)
                st.session_state.messages.append({"role": "assistant", "content": cevap})
                st.session_state.last_assistant_text = cevap
            except Exception as e:
                st.error(f"Hata: {e}")

        st.session_state.process_mode = None

    # MİKROFON (ANA EKRANDA, SABİT)
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

    # 🔊 SON CEVABI DİNLE
    listen_c1, listen_c2 = st.columns([1, 3])
    with listen_c1:
        if st.button("🔊 Son cevabı dinle", use_container_width=True):
            if st.session_state.get("last_assistant_text", "").strip():
                try:
                    audio_mp3 = tts_bytes(st.session_state.last_assistant_text)
                    st.audio(audio_mp3, format="audio/mp3")
                    st.caption("Metin ekranda akıyor. Dinlerken takip edebilirsin.")
                except Exception as e:
                    st.error(f"Sesli okuma hatası: {e}")
            else:
                st.warning("Dinlenecek bir cevap yok.")

    # KLAVYEDEN SORU
    soru = st.chat_input("Sorunu yaz")
    if soru:
        soruyu_isle(soru, pdf_text, extra_text)
