import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

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
sheet = gc.open_by_url(st.secrets["GSHEET_URL"]).sheet1  # ilk sayfa

# ------------------ LOG FONKSİYONU ------------------
def log_yaz(kullanici, tip, mesaj):
    """Kullanıcı hareketlerini Google Sheet'e yazar."""
    try:
        sheet.append_row(
            [
                datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                kullanici,
                tip,
                mesaj,
            ]
        )
    except Exception as e:
        # Hata varsa ekranda gör
        st.error(f"Google Sheets'e yazarken hata oluştu: {e}")

# Sidebar'da manuel test butonu (şüphe varsa basıp sheet'i kontrol et)
st.sidebar.button(
    "🧪 Log Test Satırı Yaz",
    on_click=lambda: log_yaz("TEST_KULLANICI", "TEST", "Bu bir deneme satırıdır."),
)

# ------------------ GİRİŞ EKRANI ------------------
if "user" not in st.session_state:
    st.subheader("👋 Hoş geldin Dostum")
    isim = st.text_input("Adını yaz:")

    if st.button("Giriş Yap") and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.messages = []  # sohbet geçmişi (oturum içi)
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

    # -------- METİN YAPIŞTIRMA --------
    st.sidebar.header("📝 Metin Yapıştır")
    extra_text = st.sidebar.text_area("Metni buraya yapıştır", height=150)

    # -------- MODLAR --------
    st.sidebar.header("⚙️ Modlar")
    sade = st.sidebar.checkbox("🅰️ Basitleştirerek anlat")
    maddeler = st.sidebar.checkbox("🅱️ Madde madde açıkla")

    # -------- SOHBET GEÇMİŞİ ÇİZ --------
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # -------- SORU AL --------
    soru = st.chat_input("Sorunu yaz")

    if soru:
        # Kullanıcıya gösterilen soru
        with st.chat_message("user"):
            st.write(soru)

        log_yaz(st.session_state.user, "USER", soru)

        # Model için prompt hazırlama
        kullanici_istegi = soru
        if sade:
            kullanici_istegi = (
                "Bu soruyu 5. sınıf seviyesinde, basit ve kısa cümlelerle açıkla:\n"
                + kullanici_istegi
            )
        if maddeler:
            kullanici_istegi = "Cevabı madde madde yaz. " + kullanici_istegi

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

        # geçmişe ekle
        st.session_state.messages.append({"role": "user", "content": tam_soru})

        # -------- OPENAI İSTEK --------
        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_prompt}, *st.session_state.messages],
                )

                cevap = response.choices[0].message.content
                st.write(cevap)

                st.session_state.messages.append(
                    {"role": "assistant", "content": cevap}
                )
                log_yaz(st.session_state.user, "BOT", cevap)

            except Exception as e:
                st.error(f"Hata: {e}")
