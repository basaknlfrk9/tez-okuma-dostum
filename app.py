import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import pandas as pd
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
sheet = gc.open_by_url(st.secrets["GSHEET_URL"]).sheet1


# ------------------ KELİME İSTATİSTİĞİ ------------------
def kelime_istatistikleri(metinler):
    """
    Öğrencinin yazdığı/söylediği tüm metinlerden:
    - en çok kullanılan kelimeyi
    - ilk 5 sık kelimeyi (kelime (adet) şeklinde)
    döndürür.
    """
    if not metinler:
        return "", ""

    text = " ".join(metinler).lower()
    # harf/rakam dizilerini kelime kabul et
    tokens = re.findall(r"\w+", text, flags=re.UNICODE)

    # çok sık ve anlamsız kelimeleri at (Türkçe basit stopword listesi)
    stop = {
        "ve", "veya", "ile", "ama", "fakat", "çünkü",
        "ben", "sen", "o", "biz", "siz", "onlar",
        "bu", "şu", "o", "bir", "iki", "üç",
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


# ------------------ OTURUM ÖZETİ YAZ ------------------
def oturum_ozeti_yaz():
    """
    Çıkışta:
    - giriş saati
    - çıkış saati
    - kaç dakika kalmış
    - en çok kullandığı kelime
    - en sık geçen 5 kelime
    bilgilerini tek satır olarak Google Sheet'e yazar.
    BOT cevabı hiç kaydedilmez.
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
        # Sütun sırası: Kullanici | Giris | Cikis | Dakika | EnCokKelime | SikKelimeler
        sheet.append_row(
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


# ------------------ SORU CEVAPLAMA (HER SORU BAĞIMSIZ) ------------------
def soruyu_isle(soru: str, pdf_text: str, extra_text: str):
    """
    PDF/metin + soruyu kullanarak cevap üretir.
    Model her seferinde sadece BU soruyu görür; önceki sohbeti bağlama göndermez.
    """

    # Sohbet alanında kullanıcı balonu
    with st.chat_message("user"):
        st.write(soru)

    # Ekranda gösterilecek geçmiş için
    st.session_state.messages.append({"role": "user", "content": soru})

    # Öğrenci analizinde kullanmak için (kelime istatistiği)
    st.session_state.user_texts.append(soru)

    # PDF + ekstra metni bağlama ekle
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

    # MODEL ARTIK SADECE BU SORUYU GÖRÜYOR
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

            # Ekranda geçmiş için (ama SHEET'e yazmıyoruz)
            st.session_state.messages.append(
                {"role": "assistant", "content": cevap}
            )

        except Exception as e:
            st.error(f"Hata: {e}")


# ------------------ GİRİŞ EKRANI ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        isim = isim.strip()
        st.session_state.user = isim
        st.session_state.messages = []      # sadece ekranda göstermek için
        st.session_state.user_texts = []    # analiz için öğrenci soruları
        st.session_state.start_time = datetime.now(ZoneInfo("Europe/Istanbul"))
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    # ======== YAN PANEL ========
    st.sidebar.success(f"Hoş geldin dostum 🌈 {st.session_state.user}")

    if st.sidebar.button("Çıkış Yap"):
        # Burada sadece ÖZET satırı yazıyoruz
        oturum_ozeti_yaz()
        st.session_state.clear()
        st.rerun()

    # PDF
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

    # ------------- METNİ İŞLE (YAN PANEL) -------------
    st.sidebar.header("⚙️ Metni işle")

    if "process_mode" not in st.session_state:
        st.session_state.process_mode = None

    if st.sidebar.button("🅰️ Metni basitleştir"):
        if not (pdf_text or extra_text):
            st.sidebar.warning("Önce PDF yükle veya metin yapıştır 😊")
        else:
            st.session_state.process_mode = "basit"

    if st.sidebar.button("🧩 Metni madde madde açıkla"):
        if not (pdf_text or extra_text):
            st.sidebar.warning("Önce PDF yükle veya metin yapıştır 😊")
        else:
            st.session_state.process_mode = "madde"

    # ======== ORTA ALAN (SOHBET) ========

    # Eski mesajları göster (sadece bu oturum)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # ------------- 🎤 MİKROFONLA SORU SOR -------------
    st.markdown("### 🎤 Mikrofonla soru sor")
    audio_bytes = audio_recorder(
        text="Kaydı başlat / durdur",
        pause_threshold=2.0,
        sample_rate=16000,
        key="mic_recorder_main",
    )

    if audio_bytes:
        # sadece YENİ kayıtları işle
        last_len = st.session_state.get("last_audio_len", 0)
        if len(audio_bytes) != last_len:
            st.session_state["last_audio_len"] = len(audio_bytes)

            st.info(f"Ses kaydı alındı (byte uzunluğu: {len(audio_bytes)})")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as f:
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="tr",
                    )
                    mic_text = transcript.text
                    st.write(f"🎧 Anlaşılan soru: _{mic_text}_")
                    # mikrofon sorusu da bir öğrenci sorusu → analiz için ekle
                    soruyu_isle(mic_text, pdf_text, extra_text)
                except Exception as e:
                    st.error(f"Ses yazıya çevrilirken hata: {e}")

    # ------------- METNİ İŞLEME ÇIKTISI -------------
    if st.session_state.get("process_mode") in ("basit", "madde") and (pdf_text or extra_text):
        kaynak_metin = (pdf_text + "\n" + extra_text).strip()

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
                # Bu cevaplar da sadece ekranda dursun, sheet'e yazmıyoruz
                st.session_state.messages.append(
                    {"role": "assistant", "content": cevap}
                )
            except Exception as e:
                st.error(f"Hata: {e
