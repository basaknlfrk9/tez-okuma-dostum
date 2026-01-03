import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re
import json
import uuid
import time
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — ÖÖG & GELİŞİM TAKİP SİSTEMİ (NİHAİ)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ÖÖG Dostu Görsel Stil (Büyük font, geniş satır aralığı)
st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    p, li, div, span { line-height: 2.1 !important; word-spacing: 0.15em !important; }
    .stButton button { font-size: 20px !important; border-radius: 15px !important; padding: 12px !important; }
    .highlight-box {
        background-color: #fcfcfc; padding: 30px; border-radius: 20px;
        border: 2px solid #e0e0e0; font-size: 24px !important; margin-bottom: 20px;
    }
    .card { border: 1px solid #ddd; border-radius: 15px; padding: 20px; background: white; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ Sheets Bağlantısı ------------------
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
gc = gspread.authorize(credentials)
workbook = gc.open_by_url(st.secrets["GSHEET_URL"])
perf_sheet = workbook.worksheet("Performans")

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

# ------------------ Seslendirme (TTS) ------------------
def tts_bytes(text: str) -> bytes:
    clean_text = re.sub(r"[*#_]", "", text)
    mp3_fp = BytesIO()
    gTTS(clean_text[:1000], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

# ------------------ AI Zekası (ÖÖG Sadeleştirme) ------------------
def get_ai_activity(source_text: str):
    system_prompt = """
    Sen ÖÖG (Disleksi) uzmanı bir Türkçe öğretmenisin. 
    1) 'sade_metin': Metni 5-8. sınıf seviyesinde, kısa cümlelerle, somutlaştırarak yeniden yaz.
    2) 'kelimeler': Metindeki 3 zor kelime ve basit anlamı.
    3) 'sorular': 6 adet (A,B,C) çoktan seçmeli soru. Türler: 'bilgi', 'cikarim', 'ana_fikir', 'baslik', 'kelime'.
    Çıktı sadece JSON olsun.
    """
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Metin: {source_text}"}
        ],
        response_format={ "type": "json_object" }
    )
    return json.loads(resp.choices[0].message.content)

# ------------------ Gelişim Kayıt (Tablonuza Uygun) ------------------
def performans_kaydet_to_sheets():
    # Süre ve Başarı Hesapla
    sure_saniye = time.time() - st.session_state.start_time_stamp
    dakika = round(sure_saniye / 60, 2)
    
    act = st.session_state.activity
    dogru_sayisi = sum(st.session_state.correct_map.values())
    basari_yuzde = round((dogru_sayisi / 6) * 100, 1)
    
    # Hatalı Kazanımları Bul (Gelişim takibi için kritik)
    hatalar = []
    for i, q in enumerate(act['sorular']):
        if st.session_state.correct_map.get(i) == 0:
            hatalar.append(q.get('tur', 'genel'))
    kazanim_notu = ", ".join(set(hatalar)) if hatalar else "Eksik Yok"

    # Tablodaki A'dan J'ye kadar olan sütunlar
    row = [
        st.session_state.user,          # A: Kullanici
        st.session_state.login_time,    # B: Giris
        now_tr_str(),                   # C: Cikis
        dakika,                         # D: Dakika
        st.session_state.sinif,         # E: Sinif
        f"%{basari_yuzde}",             # F: Basari_Yuzdesi
        dogru_sayisi,                   # G: Dogru_Sayisi
        st.session_state.total_ipucu,   # H: Ipucu_Sayisi
        kazanim_notu,                   # I: Hatali_Kazanimlar
        st.session_state.metin_id       # J: Metin_ID
    ]
    perf_sheet.append_row(row)

# =========================================================
# UYGULAMA AKIŞI
# =========================================================

if "user" not in st.session_state:
    st.title("📚 Okuma Dostum")
    st.session_state.user = st.text_input("Adın:")
    st.session_state.sinif = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
    if st.button("Başla") and st.session_state.user:
        st.session_state.login_time = now_tr_str()
        st.session_state.phase = "setup"
        st.rerun()
    st.stop()

# Üst Bilgi
st.write(f"👤 {st.session_state.user} | {st.session_state.sinif}. Sınıf")

# 1. KURULUM (Öğretmen Metni Yükler)
if st.session_state.phase == "setup":
    st.subheader("Öğretmen Paneli: Metni Hazırla")
    m_id = st.text_input("Metin ID (Örn: Ünite1_Metin1)")
    uploaded_file = st.file_uploader("MEB PDF Yükle", type="pdf")
    pasted_text = st.text_area("Veya Metni Yapıştır")
    
    if st.button("Çalışmayı Başlat"):
        raw = pasted_text
        if uploaded_file:
            reader = PdfReader(uploaded_file)
            raw = "\n".join([p.extract_text() for p in reader.pages])
        
        with st.spinner("ÖÖG seviyesine göre düzenleniyor..."):
            st.session_state.activity = get_ai_activity(raw)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"
            st.session_state.start_time_stamp = time.time() # Dakika ölçümü için
            st.session_state.q_index = 0
            st.session_state.correct_map = {}
            st.session_state.total_ipucu = 0
            st.rerun()

# 2. OKUMA AŞAMASI
elif st.session_state.phase == "read":
    act = st.session_state.activity
    st.markdown(f"<div class='highlight-box'>{act['sade_metin']}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔊 Dinle", use_container_width=True):
            st.audio(tts_bytes(act['sade_metin']))
    with col2:
        if st.button("✅ Okudum, Sorulara Geç", use_container_width=True):
            st.session_state.phase = "questions"
            st.rerun()

# 3. SORULAR AŞAMASI
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    idx = st.session_state.q_index
    
    if idx < len(act['sorular']):
        q = act['sorular'][idx]
        st.markdown(f"<div class='card'><b>Soru {idx+1}:</b> {q['kok']}</div>", unsafe_allow_html=True)
        
        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q[opt]}", key=f"btn_{idx}_{opt}"):
                st.session_state.correct_map[idx] = 1 if opt == q['dogru'] else 0
                st.session_state.q_index += 1
                st.rerun()
        
        if st.button("💡 İpucu Al"):
            st.session_state.total_ipucu += 1
            st.info(q.get('ipucu', 'Metne tekrar göz at!'))
    else:
        with st.spinner("Sonuçlar kaydediliyor..."):
            performans_kaydet_to_sheets()
            st.session_state.phase = "done"
            st.rerun()

# 4. BİTİŞ
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Harika! Çalışma bitti ve öğretmenine gönderildi.")
    if st.button("Yeni Çalışma Yap"):
        st.session_state.phase = "setup"
        st.rerun()
