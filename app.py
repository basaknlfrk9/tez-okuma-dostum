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

# ------------------ SAYFA AYARI ------------------
st.set_page_config(page_title="Okuma Dostum", layout="wide")
st.title("📚 Okuma Dostum")

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

# Özet tablosu: birinci sayfa (Sheet1)
stats_sheet = workbook.sheet1

# Sohbet tablosu: "Sohbet" isminde bir sayfa (yoksa otomatik oluştur)
try:
    chat_sheet = workbook.worksheet("Sohbet")
except WorksheetNotFound:
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=1000, cols=4)
    chat_sheet.append_row(["Kullanici", "Zaman", "Rol", "Mesaj"])


# ------------------ KELİME İSTATİSTİĞİ ------------------
def kelime_istatistikleri(metinler):
    """Öğrencinin tüm sorularından kelime istatistiği çıkarır."""
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
    """
    Her mesajı 'Sohbet' sayfasına yazar:
    Kullanici | Zaman | Rol | Mesaj
    """
    try:
        now_tr = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")
        chat_sheet.append_row([user, now_tr, role, content])
    except Exception as e:
        st.error(f"Sohbet kaydedilirken hata: {e}")


def load_history(user):
    """
    Girişte, aynı isimli kullanıcının tüm eski sohbetini 'Sohbet' sayfasından okur.
    """
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
    """
    Çıkışta:
    Kullanici | Giris | Cikis | Dakika | EnCokKelime | SikKelimeler
    şeklinde TEK SATIR olarak özet tabloya yazar.
    """
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
            [
                st.session_state.user,
                giris_str,
                cikis_str,
                dakika,
                en_cok,
                diger,
            ]
        )
    except Exception as e:
        st.error(f"Oturum özeti yazılırken hata: {e}")


# ------------------ SORU CEVAPLAMA ------------------
def soruyu_isle(soru: str, pdf_text: str, extra_text: str):
    """
    PDF/metin + soruyu kullanarak cevap üretir.
    Önceki sohbeti bağlama göndermez; her soru bağımsızdır.
    """

    # Kullanıcı balonu
    with st.chat_message("user"):
        st.write(soru)

    # Ekranda geçmiş için
    st.session_state.messages.append({"role": "user", "content": soru})
    # İstatistik için
    st.session_state.user_texts.append(soru)
    # Metni işleme butonları için
    st.session_state.last_user_text = soru

    # Sheet'e kaydet (kullanıcı mesajı)
    if "user" in st.session_state:
        log_message(st.session_state.user, "user", soru)

    # Bağlam oluştur
    icerik = ""
    if pdf_text:
        icerik += "PDF metni:\n" + pdf_text[:800] + "\n\n"
    if extra_text:
        icerik += "Ek metin:\n" + extra_text[:800] + "\n\n"

    if icerik:
        tam_soru = icerik + "Öğrencinin sorusu:\n" + soru
    else:
        tam_soru = soru

    system_prompt = (
        "Sen özel öğrenme güçlüğü (disleksi vb.) yaşayan 5-8. sınıf öğrencileri için "
        "okuma dostu bir yardımcı öğretmensin. Açıklamalarını sade, kısa cümlelerle, "
        "gerektiğinde örnek vererek yap. Akademik terimleri mümkünse daha basit kelimelerle açıkla."
    )

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
            st.session_state.messages.append(
                {"role": "assistant", "content": cevap}
            )

            # Sheet'e kaydet (bot cevabı)
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

        # 📥 Eski sohbeti Google Sheet'ten yükle
        st.session_state.messages = load_history(isim)

        # Yeni oturum için istatistik alanları
        st.session_state.user_texts = []
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.session_state.process_mode = None
        st.session_state.last_audio_len = 0
        st.session_state.last_user_text = ""
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    # Eksik state'leri tamamla
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_texts" not in st.session_state:
        st.session_state.user_texts = []
    if "start_time" not in st.session_state:
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
    if "process_mode" not in st.session_state:
        st.session_state.process_mode = None
    if "last_audio_len" not in st.session_state:
        st.session_state.last_audio_len = 0
    if "last_user_text" not in st.session_state:
        st.session_state.last_user_text = ""

    # ========= YAN PANEL =========
    st.sidebar.success(f"Hoş geldin dostum 🌈 {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        oturum_ozeti_yaz()
        st.session_state.clear()
        st.rerun()

    # PDF yükle
    st.sidebar.header("📄 PDF Yükle")
    pdf_text = ""
    pdf_file = st.sidebar.file_uploader("PDF seç", type="pdf")
    if pdf_file is not None:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pdf_text += txt + "\n"

    # Metin yapıştır
    st.sidebar.header("📝 Metin Yapıştır")
    extra_text = st.sidebar.text_area("Metni buraya yapıştır", height=150)

    # Metni işle
    st.sidebar.header("⚙️ Metni işle")

    if st.sidebar.button("🅰️ Metni basitleştir"):
        if not (pdf_text or extra_text or st.session_state.last_user_text):
            st.sidebar.warning("Önce PDF yükle, metin yapıştır veya bir metin söyle 😊")
        else:
            st.session_state.process_mode = "basit"

    if st.sidebar.button("🧩 Metni madde madde açıkla"):
        if not (pdf_text or extra_text or st.session_state.last_user_text):
            st.sidebar.warning("Önce PDF yükle, metin yapıştır veya bir metin söyle 😊")
        else:
            st.session_state.process_mode = "madde"

    # 🎤 MİKROFON – YAN PANELDE SABİT VE SAĞLAM
    st.sidebar.header("🎤 Mikrofonla soru sor")

    with st.sidebar.container(border=True):
        st.markdown("**🔴 Mikrofon (ses al/durdur)**")

        audio_bytes = audio_recorder(
            text="Konuşmak için tıkla",
            pause_threshold=1.8,
            sample_rate=16000,
            key="mic_box",
        )

        st.markdown(
            "<small style='opacity:0.6'>🎙️ Mikrofon sabit modda çalışıyor.</small>",
            unsafe_allow_html=True,
        )

        if audio_bytes:
            # Yeni kayıt mı kontrol et
            last_len = st.session_state.get("last_audio_len", 0)
            if len(audio_bytes) != last_len:
                st.session_state["last_audio_len"] = len(audio_bytes)
                st.sidebar.success("Ses alındı ✔️ Yazıya çevriliyor...")

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

                    st.sidebar.info(f"📝 Sesli soru: **{mic_text}**")
                    soruyu_isle(mic_text, pdf_text, extra_text)

                except Exception as e:
                    st.sidebar.error(f"Ses yazıya çevrilirken hata oluştu: {e}")

    # ========= ORTA ALAN (SOHBET) =========

    # Geçmiş mesajları göster
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # Metni işleme çıktısı (butonlardan)
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
                st.markdown("### 🅰️ Metnin basitleştirilmiş hali")
                system_prompt = (
                    "Sen metinleri öğrenciler için sadeleştiren, "
                    "özel öğrenme güçlüğüne duyarlı bir okuma yardımcısın."
                )
                user_content = (
                    "Aşağıdaki metni 5. sınıf seviyesinde, "
                    "kısa ve basit cümlelerle açıkla:\n\n" + kaynak_metin
                )
            else:
                st.markdown("### 🧩 Metnin madde madde açıklaması")
                system_prompt = (
                    "Sen metinleri öğrenciler için özetleyen, "
                    "özel öğrenme güçlüğüne duyarlı bir okuma yardımcısın."
                )
                user_content = (
                    "Aşağıdaki metnin en önemli noktalarını madde madde çıkar:\n\n"
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
                st.session_state.messages.append(
                    {"role": "assistant", "content": cevap}
                )
            except Exception as e:
                st.error(f"Hata: {e}")

        st.session_state.process_mode = None

    # Klavyeden soru
    soru = st.chat_input("Sorunu yaz")
    if soru:
        soruyu_isle(soru, pdf_text, extra_text)
