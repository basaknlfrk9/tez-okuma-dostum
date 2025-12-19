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


# ------------------ LOG FONKSİYONU ------------------
def log_yaz(kullanici: str, tip: str, mesaj: str):
    """Kullanıcı hareketlerini Google Sheet'e yazar (Türkiye saatiyle)."""
    try:
        now_tr = datetime.now(ZoneInfo("Europe/Istanbul"))
        sheet.append_row(
            [
                now_tr.strftime("%d.%m.%Y %H:%M:%S"),
                kullanici,
                tip,
                mesaj,
            ]
        )
    except Exception as e:
        st.error(f"Google Sheets'e yazarken hata oluştu: {e}")


# ------------------ GEÇMİŞ YÜKLE ------------------
def gecmisi_yukle(kullanici: str):
    """Google Sheet'ten verilen kullanıcıya ait sohbet geçmişini okur."""
    try:
        rows = sheet.get_all_records()
        if not rows:
            return []

        df = pd.DataFrame(rows)

        if not {"Kullanici", "Tip", "Mesaj"}.issubset(df.columns):
            return []

        df = df[df["Kullanici"] == kullanici]
        df = df[df["Tip"].isin(["USER", "BOT"])]

        mesajlar = []
        for _, r in df.iterrows():
            role = "user" if r["Tip"] == "USER" else "assistant"
            mesajlar.append({"role": role, "content": r["Mesaj"]})
        return mesajlar

    except Exception as e:
        st.error(f"Geçmiş okunurken hata: {e}")
        return []


# ------------------ ORTAK SORU CEVAPLAMA FONKSİYONU ------------------
def soruyu_isle(soru: str, pdf_text: str, extra_text: str, sade: bool, maddeler: bool):
    """Metinleri ve modları kullanarak soruyu cevaplar, ekrana ve loga yazar."""

    # Kullanıcı mesajını ekranda göster
    with st.chat_message("user"):
        st.write(soru)

    log_yaz(st.session_state.user, "USER", soru)

    # Modlara göre soru metnini düzenle
    kullanici_istegi = soru
    if sade:
        kullanici_istegi = (
            "Bu soruyu 5. sınıf seviyesinde, basit ve kısa cümlelerle açıkla:\n"
            + kullanici_istegi
        )
    if maddeler:
        kullanici_istegi = "Cevabı madde madde yaz. " + kullanici_istegi

    # PDF + ekstra metni bağlama ekle
    icerik = ""
    if pdf_text:
        icerik += "PDF metni:\n" + pdf_text[:2000] + "\n\n"
    if extra_text:
        icerik += "Ek metin:\n" + extra_text[:2000] + "\n\n"

    if icerik:
        tam_soru = icerik + "Öğrencinin sorusu:\n" + kullanici_istegi
    else:
        tam_soru = kullanici_istegi

    system_prompt = (
        "Sen özel öğrenme güçlüğü (disleksi vb.) yaşayan 5-8. sınıf öğrencileri için "
        "okuma dostu bir yardımcı öğretmensin. Açıklamalarını sade, kısa cümlelerle, "
        "gerektiğinde örnek vererek yap. Akademik terimleri mümkünse daha basit kelimelerle açıkla."
    )

    # Geçmişe ekle (model bağlamı için)
    st.session_state.messages.append({"role": "user", "content": tam_soru})

    # OpenAI isteği
    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *st.session_state.messages,
                ],
            )
            cevap = response.choices[0].message.content
            st.write(cevap)

            st.session_state.messages.append(
                {"role": "assistant", "content": cevap}
            )
            log_yaz(st.session_state.user, "BOT", cevap)

        except Exception as e:
            st.error(f"Hata: {e}")


# ------------------ GİRİŞ EKRANI ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        isim = isim.strip()
        st.session_state.user = isim
        st.session_state.messages = gecmisi_yukle(isim)
        log_yaz(isim, "SİSTEM", "Giriş yaptı")
        st.rerun()

# ------------------ ANA EKRAN ------------------
else:
    st.sidebar.success(f"Hoş geldin dostum 🌈 {st.session_state.user}")

    # Çıkış
    if st.sidebar.button("Çıkış Yap"):
        log_yaz(st.session_state.user, "SİSTEM", "Çıkış yaptı")
        st.session_state.clear()
        st.rerun()

    # -------- PDF YÜKLEME --------
    st.sidebar.header("📄 PDF Yükle")
    pdf_text = ""
    pdf_file = st.sidebar.file_uploader("PDF seç", type="pdf")

    if pdf_file is not None:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pdf_text += txt + "\n"

    # -------- METİN YAPIŞTIR --------
    st.sidebar.header("📝 Metin Yapıştır")
    extra_text = st.sidebar.text_area("Metni buraya yapıştır", height=150)

    # -------- MODLAR (SORU CEVAPLAMA İÇİN) --------
    st.sidebar.header("⚙️ Yanıt Modu (Sorular için)")
    sade = st.sidebar.checkbox("🅰️ Basitleştirerek anlat")
    maddeler = st.sidebar.checkbox("🅱️ Madde madde açıkla")

    # -------- METNİ HEMEN İŞLE BUTONLARI --------
    st.sidebar.header("🪄 Metni Hemen İşle")
    if "mode_action" not in st.session_state:
        st.session_state.mode_action = None

    if st.sidebar.button("🅰️ Metni basitleştir"):
        st.session_state.mode_action = "basit"

    if st.sidebar.button("🧩 Metni madde madde açıkla"):
        st.session_state.mode_action = "madde"

    # -------- SOHBET GEÇMİŞİNİ ÇİZ --------
    if "messages" not in st.session_state:
        st.session_state.messages = gecmisi_yukle(st.session_state.user)

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # -------- METNİ HEMEN İŞLEME ÇIKTISI --------
    if st.session_state.mode_action:
        if not (pdf_text or extra_text):
            st.warning("Önce PDF yükle veya metin yapıştır, sonra modu seç 😊")
        else:
            kaynak_metin = (pdf_text + "\n" + extra_text).strip()
            if st.session_state.mode_action == "basit":
                user_content = (
                    "Aşağıdaki metni 5. sınıf seviyesinde, "
                    "kısa ve basit cümlelerle açıkla:\n\n" + kaynak_metin
                )
                baslik = "🅰️ Metnin Basitleştirilmiş Hali"
            else:
                user_content = (
                    "Aşağıdaki metnin en önemli noktalarını madde madde çıkar:\n\n"
                    + kaynak_metin
                )
                baslik = "🧩 Metnin Madde Madde Açıklaması"

            with st.chat_message("assistant"):
                st.markdown(f"### {baslik}")
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "Sen metinleri öğrenciler için sadeleştiren, "
                                    "özel öğrenme güçlüğüne duyarlı bir okuma yardımcısın."
                                ),
                            },
                            {"role": "user", "content": user_content},
                        ],
                    )
                    cevap = response.choices[0].message.content
                    st.write(cevap)
                    log_yaz(
                        st.session_state.user,
                        "BOT",
                        f"[MOD-{st.session_state.mode_action}] {cevap}",
                    )
                except Exception as e:
                    st.error(f"Hata: {e}")

        # işlem tamamlandıktan sonra bayrağı sıfırla
        st.session_state.mode_action = None

    # -------- 🎙️ MİKROFONLA SORU SOR --------
    st.markdown("### 🎙️ Mikrofonla soru sor")
    audio_bytes = audio_recorder(
        text="Kaydı başlatmak/durdurmak için tıkla",
        pause_threshold=2.0,
        sample_rate=16000,
        key="mic_recorder",
    )

    if audio_bytes:
        # Aynı kaydı tekrar tekrar işlememek için uzunluğa göre kontrol
        last_len = st.session_state.get("last_audio_len", 0)
        if len(audio_bytes) != last_len:
            st.session_state["last_audio_len"] = len(audio_bytes)

            # geçici dosyaya yaz
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
                    st.info(f"🎧 Senden anladığım soru: _{mic_text}_")
                    # Mikrofon sorusunu normal soru akışından geçir
                    soruyu_isle(mic_text, pdf_text, extra_text, sade, maddeler)
                except Exception as e:
                    st.error(f"Ses yazıya çevrilirken hata: {e}")

    # -------- KLAVYE İLE SORU AL --------
    soru = st.chat_input("Sorunu yaz")

    if soru:
        soruyu_isle(soru, pdf_text, extra_text, sade, maddeler)
