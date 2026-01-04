import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import json, uuid, time
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — ÖÖG DESTEKLİ & CHAT ÖZELLİKLİ TAM KOD
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# 1. ÖÖG DOSTU RENKLİ TASARIM
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 22px; }
    .stButton button { 
        width: 100%; border-radius: 20px; height: 3.5em; 
        font-weight: 600; font-size: 20px !important; transition: 0.3s;
        border: 2px solid #ddd;
    }
    /* Renkli Butonlar */
    div.stButton > button:first-child { background-color: #4A90E2; color: white; } /* Mavi */
    div.stButton > button:hover { opacity: 0.8; transform: scale(1.02); }
    .chat-box { background-color: #f9f9f9; padding: 20px; border-radius: 15px; border: 1px solid #eee; margin-top: 20px; }
    .highlight-box { 
        background-color: #ffffff; padding: 30px; border-radius: 25px; 
        box-shadow: 0 8px 16px rgba(0,0,0,0.05); border-left: 10px solid #FFD700;
        font-size: 26px !important; line-height: 2 !important; margin-bottom: 25px;
    }
</style>
""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 2. VERİ KAYIT FONKSİYONU
def save_data(row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        ws = sh.get_worksheet(0) # İlk sayfaya yazar
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"⚠️ Kayıt Hatası: {str(e)}")
        return False

# 3. SES DOSYASI ÜRETİCİ
def get_audio(text):
    tts = gTTS(text=text, lang='tr')
    fp = BytesIO()
    tts.write_to_fp(fp)
    return fp

# --- OTURUM YÖNETİMİ ---
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "messages" not in st.session_state: st.session_state.messages = []

# Üst Bar & Çıkış
if st.session_state.phase != "auth":
    c1, c2 = st.columns([9, 1])
    with c2: 
        if st.button("Çıkış", type="secondary"): 
            st.session_state.clear(); st.rerun()

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Adın:")
    s = st.selectbox("Sınıfın:", ["5. Sınıf", "6. Sınıf", "7. Sınıf", "8. Sınıf"])
    if st.button("Başla 🚀") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
        st.session_state.phase = "setup"; st.rerun()

# 2. KURULUM
elif st.session_state.phase == "setup":
    st.header("Metin Hazırlama")
    m_id = st.text_input("Metin ID:", "Metin_1")
    up = st.file_uploader("PDF Yükle", type="pdf")
    txt = st.text_area("Veya Metni Buraya Yaz")
    
    if st.button("Hazırla ✨") and (up or txt):
        raw = txt
        if up: raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        
        with st.spinner("Senin için harika bir metin oluşturuyorum..."):
            prompt = "ÖÖG uzmanı olarak metni ortaokul seviyesinde sadeleştir. 6 soru (bilgi, cikarim, ana_fikir) içeren JSON üret."
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw}],
                response_format={ "type": "json_object" }
            )
            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"; st.session_state.start_t = time.time()
            st.session_state.q_idx = 0; st.session_state.correct_map = {}; st.session_state.hints = 0
            st.rerun()

# 3. OKUMA & SOHBET
elif st.session_state.phase == "read":
    metin = st.session_state.activity['sade_metin']
    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 5])
    with col1:
        if st.button("🔊 Metni Dinle"):
            st.audio(get_audio(metin), format="audio/mp3")
    
    # --- SOHBET / CHAT KISMI ---
    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor")
    user_q = st.chat_input("Metinde anlamadığın bir yer var mı?")
    if user_q:
        with st.spinner("Düşünüyorum..."):
            ai_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"Sen bir ÖÖG öğretmenisin. Şu metne göre cevap ver: {metin}"},
                    {"role": "user", "content": user_q}
                ]
            )
            st.info(ai_resp.choices[0].message.content)
    
    if st.button("Sorulara Geç ➔"):
        st.session_state.phase = "questions"; st.rerun()

# 4. SORULAR
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    i = st.session_state.q_idx

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1}")
        st.info(q['kok'])
        
        c_a, c_b, c_c = st.columns(3)
        with c_a: 
            if st.button(f"A) {q['A']}", key=f"a{i}"):
                st.session_state.correct_map[i] = 1 if q['dogru']=="A" else 0
                if q['dogru']=="A": st.success("Doğru!"); time.sleep(1); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Tekrar Dene!")
        with c_b:
            if st.button(f"B) {q['B']}", key=f"b{i}"):
                st.session_state.correct_map[i] = 1 if q['dogru']=="B" else 0
                if q['dogru']=="B": st.success("Doğru!"); time.sleep(1); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Tekrar Dene!")
        with c_c:
            if st.button(f"C) {q['C']}", key=f"c{i}"):
                st.session_state.correct_map[i] = 1 if q['dogru']=="C" else 0
                if q['dogru']=="C": st.success("Doğru!"); time.sleep(1); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Tekrar Dene!")
        
        if st.button("💡 İpucu"):
            st.session_state.hints += 1
            st.warning(q['ipucu'])
    else:
        # BİTİR VE KAYDET
        dogru = sum(st.session_state.correct_map.values())
        sure = round((time.time()-st.session_state.start_t)/60, 2)
        row = [st.session_state.session_id, st.session_state.user, st.session_state.login_time, 
               sure, st.session_state.sinif, f"%{round(dogru/6*100)}", 6, dogru, "ÖÖG Analiz", 
               st.session_state.metin_id, st.session_state.hints]
        
        if save_data(row):
            st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.balloons()
    st.title("🎉 Tebrikler!")
    st.write("Çalışman başarıyla kaydedildi.")
    if st.button("Yeni Metin"): st.session_state.phase = "setup"; st.rerun()
