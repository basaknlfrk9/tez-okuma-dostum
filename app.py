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
# OKUMA DOSTUM — FULL ÖZELLİK + HATA KORUMALI KAYIT
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide", initial_sidebar_state="collapsed")

# 1. ŞIK TASARIM (CSS)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; font-size: 20px; }
    .main { background-color: #f0f2f6; }
    .stButton button { 
        width: 100%; border-radius: 12px; height: 3em; 
        background-color: #4A90E2; color: white; border: none;
        transition: 0.3s; font-weight: 600;
    }
    .stButton button:hover { background-color: #357ABD; border: none; color: white; }
    .highlight-box { 
        background-color: white; padding: 30px; border-radius: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); line-height: 1.8;
        font-size: 24px !important; margin-bottom: 20px; border-left: 8px solid #4A90E2;
    }
    .status-bar { padding: 10px; border-radius: 10px; background: #ebf3fb; margin-bottom: 20px; border: 1px solid #cce5ff; }
</style>
""", unsafe_allow_html=True)

# 2. BAĞLANTI AYARLARI
def get_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def save_performance(row):
    """Google Sheets'e veri kaydeder ve hata varsa ekrana basar."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        
        # Sayfayı isme göre ara, yoksa ilk sayfayı al
        try:
            ws = sh.worksheet("Performans")
        except:
            ws = sh.get_worksheet(0)
            
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"⚠️ KAYIT BAŞARISIZ: {str(e)}") # Buradaki hata mesajı bize her şeyi anlatacak
        return False

# 3. SESLİ DİNLEME FONKSİYONU
def speak_text(text):
    try:
        tts = gTTS(text=text, lang='tr')
        fp = BytesIO()
        tts.write_to_fp(fp)
        return fp
    except:
        return None

# --- UYGULAMA AKIŞI ---
if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# ÇIKIŞ BUTONU (Her zaman sağ üstte)
if st.session_state.phase != "auth":
    col_out1, col_out2 = st.columns([9, 1])
    with col_out2:
        if st.button("Çıkış"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum'a Hoş Geldin")
    with st.container():
        u = st.text_input("Adın Soyadın:")
        s = st.selectbox("Sınıfın:", ["5. Sınıf", "6. Sınıf", "7. Sınıf", "8. Sınıf"])
        if st.button("Başla") and u:
            st.session_state.user = u
            st.session_state.sinif = s
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
            st.session_state.phase = "setup"; st.rerun()

# 2. METİN YÜKLEME
elif st.session_state.phase == "setup":
    st.subheader(f"Merhaba {st.session_state.user}, bugün ne okumak istersin?")
    m_id = st.text_input("Metin Adı/ID:", "Metin_1")
    up = st.file_uploader("PDF Yükle", type="pdf")
    txt = st.text_area("Veya Metni Buraya Yapıştır")
    
    if st.button("Materyali Hazırla") and (up or txt):
        raw = txt
        if up:
            raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        
        with st.spinner("Yapay zeka metni senin için düzenliyor..."):
            client = get_client()
            prompt = "ÖÖG uzmanı olarak metni sadeleştir ve 6 çoktan seçmeli soru içeren JSON üret. Format: {'sade_metin': '...', 'sorular': [{'kok': '...', 'A': '...', 'B': '...', 'C': '...', 'dogru': 'A', 'ipucu': '...'}]}"
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw}],
                response_format={ "type": "json_object" }
            )
            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"
            st.session_state.start_time = time.time()
            st.session_state.q_idx = 0
            st.session_state.correct_map = {}
            st.session_state.total_ipucu = 0
            st.rerun()

# 3. OKUMA VE SES
elif st.session_state.phase == "read":
    metin = st.session_state.activity.get('sade_metin', '')
    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔊 Dinle"):
            audio = speak_text(metin)
            if audio: st.audio(audio, format="audio/mp3")
    
    if st.button("Okudum, Sorulara Geç ➔"):
        st.session_state.phase = "questions"; st.rerun()

# 4. SORULAR
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    idx = st.session_state.q_idx

    if idx < len(sorular):
        q = sorular[idx]
        st.markdown(f"### Soru {idx + 1}")
        st.info(q.get('kok'))
        
        for o in ["A", "B", "C"]:
            if st.button(f"{o}) {q.get(o)}", key=f"btn_{idx}_{o}"):
                if o == q.get('dogru'):
                    st.session_state.correct_map[idx] = st.session_state.correct_map.get(idx, 1)
                    st.success("Tebrikler! Doğru.")
                    time.sleep(1)
                    st.session_state.q_idx += 1; st.rerun()
                else:
                    st.session_state.correct_map[idx] = 0
                    st.error("Bu cevap doğru değil, tekrar deneyebilirsin.")
        
        if st.button("💡 İpucu Al"):
            st.session_state.total_ipucu += 1
            st.warning(q.get('ipucu'))
    else:
        # KAYIT VE BİTİŞ
        dogru_sayisi = sum(st.session_state.correct_map.values())
        sure = round((time.time() - st.session_state.start_time)/60, 2)
        basari = f"%{round((dogru_sayisi/len(sorular))*100)}"
        
        row = [
            st.session_state.session_id,  # A
            st.session_state.user,        # B
            st.session_state.login_time,  # C
            sure,                         # D
            st.session_state.sinif,       # E
            basari,                       # F
            len(sorular),                 # G
            dogru_sayisi,                 # H
            "Analiz Bekleniyor",          # I
            st.session_state.metin_id,    # J
            st.session_state.total_ipucu  # K
        ]
        
        with st.spinner("Sonuçlar kaydediliyor..."):
            if save_performance(row):
                st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.balloons()
    st.title("🎉 Harika İş Çıkardın!")
    st.write(f"Tüm soruları tamamladın. Sonuçların öğretmeninle paylaşıldı.")
    if st.button("Yeni Bir Metne Başla"):
        st.session_state.phase = "setup"; st.rerun()
