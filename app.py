import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import json, uuid, time, re
from gtts import gTTS
from io import BytesIO

# =========================================================
# ÖÖG DOSTU TASARIM VE GELİŞMİŞ SOHBET SİSTEMİ
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# 1. RENKLİ VE BÜYÜK BUTON TASARIMI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 22px; }
    
    /* Butonları Renkli ve Belirgin Yapalım */
    .stButton button { 
        width: 100%; border-radius: 20px; height: 3.5em; 
        font-weight: 600; font-size: 22px !important; transition: 0.3s;
        border: 3px solid #eee;
    }
    /* Mavi Buton - İlerleme */
    div.stButton > button { background-color: #3498db; color: white; }
    /* Yeşil Buton - Onay */
    div.stButton > button[kind="primary"] { background-color: #2ecc71; color: white; }
    
    .highlight-box { 
        background-color: #ffffff; padding: 35px; border-radius: 30px; 
        box-shadow: 0 10px 20px rgba(0,0,0,0.08); border-left: 15px solid #f1c40f;
        font-size: 26px !important; line-height: 2.2 !important; margin-bottom: 30px;
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# 2. GÜVENLİ BAĞLANTI KONTROLÜ
def get_ai_client():
    try:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except:
        st.error("OpenAI Anahtarı eksik! Lütfen Secrets ayarlarını kontrol edin.")
        st.stop()

client = get_ai_client()

# 3. VERİ KAYIT FONKSİYONU (HATA AYIKLAMALI)
def save_to_sheets(row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        # 'Performans' adında sayfa arar, yoksa ilk sayfaya yazar
        try:
            ws = sh.worksheet("Performans")
        except:
            ws = sh.get_worksheet(0)
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"⚠️ VERİ KAYDEDİLEMEDİ: {str(e)}")
        return False

# 4. SESLİ DESTEK
def get_audio(text):
    tts = gTTS(text=re.sub(r"[*#_]", "", text)[:1000], lang='tr')
    fp = BytesIO()
    tts.write_to_fp(fp)
    return fp

# --- OTURUM BAŞLATMA ---
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# Global Çıkış Butonu
if st.session_state.phase != "auth":
    col_x, col_y = st.columns([9, 1])
    with col_y:
        if st.button("Çıkış 🚪"):
            st.session_state.clear(); st.rerun()

# 1. GİRİŞ EKRANI
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Adın Soyadın:")
    s = st.selectbox("Sınıfın:", ["5. Sınıf", "6. Sınıf", "7. Sınıf", "8. Sınıf"])
    if st.button("Hadi Başlayalım! 🚀") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
        st.session_state.phase = "setup"; st.rerun()

# 2. KURULUM
elif st.session_state.phase == "setup":
    st.subheader("Okuyacağımız Metni Hazırlayalım")
    m_id = st.text_input("Metin ID:", "Metin_1")
    up = st.file_uploader("Metni PDF olarak yükle", type="pdf")
    txt = st.text_area("Veya metni buraya kopyala")
    
    if st.button("Metni Hazırla ✨") and (up or txt):
        raw = txt
        if up: raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        
        with st.spinner("Metni senin için sadeleştiriyorum..."):
            prompt = "ÖÖG uzmanı olarak metni ortaokul öğrencisi için sadeleştir ama çok kısaltma. 6 soru içeren JSON üret."
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw}],
                response_format={ "type": "json_object" }
            )
            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"; st.session_state.q_idx = 0
            st.session_state.correct_map = {}; st.session_state.hints = 0
            st.session_state.start_t = time.time()
            st.rerun()

# 3. OKUMA VE SOHBET (KeyError Çözüldü)
elif st.session_state.phase == "read":
    # KeyError korumalı metin çekme
    metin = st.session_state.activity.get('sade_metin') or st.session_state.activity.get('metin') or "Metin yüklenemedi."
    
    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Sesli Dinle"):
            st.audio(get_audio(metin), format="audio/mp3")
    
    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor")
    user_q = st.chat_input("Metinde anlamadığın bir kelime veya yer var mı?")
    if user_q:
        with st.spinner("Cevap yazıyorum..."):
            ai_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"Sen ÖÖG öğretmeni yardımcısısın. Öğrenciye şu metne göre destek ol: {metin}"},
                    {"role": "user", "content": user_q}
                ]
            )
            st.session_state.chat_history.append({"q": user_q, "a": ai_resp.choices[0].message.content})
    
    for chat in st.session_state.chat_history:
        st.chat_message("user").write(chat['q'])
        st.chat_message("assistant").write(chat['a'])
    
    if st.button("Sorulara Geç ➔"):
        st.session_state.phase = "questions"; st.rerun()

# 4. SORULAR (Renkli Butonlu)
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    i = st.session_state.q_idx

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")
        st.markdown(f"<div style='font-size:24px; color:#2c3e50; margin-bottom:20px;'>{q.get('kok')}</div>", unsafe_allow_html=True)
        
        c_a, c_b, c_c = st.columns(3)
        with c_a: 
            if st.button(f"A) {q.get('A')}", key=f"a{i}"):
                if q.get('dogru')=="A": 
                    st.session_state.correct_map[i] = 1; st.success("🌟 Mükemmel! Doğru."); time.sleep(1.2); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Bu cevap olmadı, tekrar dene!"); st.session_state.correct_map[i] = 0
        with c_b:
            if st.button(f"B) {q.get('B')}", key=f"b{i}"):
                if q.get('dogru')=="B": 
                    st.session_state.correct_map[i] = 1; st.success("🌟 Harika! Doğru."); time.sleep(1.2); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Farklı bir şık dene!"); st.session_state.correct_map[i] = 0
        with c_c:
            if st.button(f"C) {q.get('C')}", key=f"c{i}"):
                if q.get('dogru')=="C": 
                    st.session_state.correct_map[i] = 1; st.success("🌟 Süpersin! Doğru."); time.sleep(1.2); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Metne tekrar bakıp dene!"); st.session_state.correct_map[i] = 0
        
        if st.button("💡 İpucu Al"):
            st.session_state.hints += 1
            st.warning(q.get('ipucu', 'Cevap metnin içinde gizli!'))
    else:
        # KAYIT SİSTEMİ (7. ve 8. Görseldeki A-O Sıralaması)
        dogru = sum(st.session_state.correct_map.values())
        sure = round((time.time()-st.session_state.start_t)/60, 2)
        row = [
            st.session_state.session_id, st.session_state.user, st.session_state.login_time, 
            sure, st.session_state.sinif, f"%{round(dogru/6*100, 1)}", 6, dogru, 
            "ÖÖG Analiz", st.session_state.metin_id, st.session_state.hints, 
            "Evet", "Evet", 0, 0
        ]
        if save_to_sheets(row):
            st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.balloons()
    st.title("🎉 Bugün Çok Başarılıydın!")
    st.success("Tüm verilerin öğretmeninle paylaşıldı.")
    if st.button("Yeni Bir Maceraya Başla"):
        st.session_state.phase = "setup"; st.rerun()
