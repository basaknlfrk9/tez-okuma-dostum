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
# OKUMA DOSTUM — ÖÖG DESTEKLİ & AKILLI REHBER SİSTEMİ
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# Tasarım ve Renkli Butonlar
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 22px; }
    .stButton button { 
        width: 100%; border-radius: 20px; height: 3.5em; 
        font-weight: 600; font-size: 22px !important; transition: 0.3s;
        border: 3px solid #eee; background-color: #3498db; color: white;
    }
    .highlight-box { 
        background-color: #ffffff; padding: 35px; border-radius: 30px; 
        box-shadow: 0 10px 20px rgba(0,0,0,0.08); border-left: 15px solid #f1c40f;
        font-size: 26px !important; line-height: 2.2 !important; margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

# GÜVENLİ BAĞLANTILAR
def get_ai_client():
    try: return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except: st.error("Lütfen Secrets alanına OPENAI_API_KEY ekleyin."); st.stop()

client = get_ai_client()

def save_to_sheets(row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        ws = sh.worksheet("Performans")
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"Veri Kayıt Hatası: {e}"); return False

def get_audio(text):
    tts = gTTS(text=re.sub(r"[*#_]", "", text)[:1000], lang='tr')
    fp = BytesIO(); tts.write_to_fp(fp); return fp

# OTURUM BAŞLATMA
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# Global Çıkış Butonu
if st.session_state.phase != "auth":
    col_x, col_y = st.columns([9, 1])
    with col_y:
        if st.button("Çıkış 🚪"): st.session_state.clear(); st.rerun()

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Adın Soyadın:")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
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
        
        with st.spinner("Metni senin için düzenliyorum..."):
            prompt = "ÖÖG uzmanı olarak metni ortaokul öğrencisi için sadeleştir. 6 soru içeren saf JSON üret. Şema: {'sade_metin': '...', 'sorular': [{'kok': '...', 'A': '...', 'B': '...', 'C': '...', 'dogru': 'A', 'tur': 'bilgi', 'ipucu': '...'}]}"
            resp = client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw}],
                response_format={ "type": "json_object" }
            )
            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"; st.session_state.q_idx = 0
            st.session_state.correct_map = {}; st.session_state.hints = 0
            st.session_state.start_t = time.time(); st.rerun()

# 3. OKUMA VE SOHBET
elif st.session_state.phase == "read":
    act = st.session_state.activity
    metin = act.get('sade_metin') or act.get('metin') or "Metin içeriği alınamadı."
    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Sesli Dinle"): st.audio(get_audio(metin), format="audio/mp3")
    
    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor")
    user_q = st.chat_input("Metinde anlamadığın bir yer var mı?")
    if user_q:
        ai_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": f"Sen ÖÖG öğretmenisin. Şu metne göre yardım et: {metin}"}, {"role": "user", "content": user_q}]
        )
        st.session_state.chat_history.append({"q": user_q, "a": ai_resp.choices[0].message.content})
    
    for chat in st.session_state.chat_history:
        st.chat_message("user").write(chat['q'])
        st.chat_message("assistant").write(chat['a'])
    
    if st.button("Sorulara Geç ➔"): st.session_state.phase = "questions"; st.rerun()

# 4. SORULAR (Görsel 10'daki A-O Sıralamasına Göre)
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    i = st.session_state.q_idx

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")
        st.markdown(f"<div style='font-size:24px; margin-bottom:20px;'>{q.get('kok')}</div>", unsafe_allow_html=True)
        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt)}", key=f"q_{i}_{opt}"):
                if opt == q.get('dogru'):
                    st.session_state.correct_map[i] = 1; st.success("🌟 Doğru!"); time.sleep(1); st.session_state.q_idx+=1; st.rerun()
                else: st.error("Tekrar dene!"); st.session_state.correct_map[i] = 0
        if st.button("💡 İpucu Al"):
            st.session_state.hints += 1; st.warning(q.get('ipucu', 'Metne bakabilirsin!'))
    else:
        # VERİ KAYIT (A'dan O'ya Kesin Eşleşme)
        dogru = sum(st.session_state.correct_map.values())
        sure = round((time.time()-st.session_state.start_t)/60, 2)
        row = [
            st.session_state.session_id,     # A: OturumID
            st.session_state.user,          # B: Kullanici
            st.session_state.login_time,    # C: TarihSaat
            sure,                           # D: SureDakika
            st.session_state.sinif,         # E: SinifDuzeyi
            f"%{round(dogru/6*100, 1)}",    # F: BasariYuzde (Eskiden MetinID olan yer düzeldi)
            6,                              # G: ToplamSoru
            dogru,                          # H: DogruSayi
            "Analiz",                       # I: HataliKazanim
            st.session_state.metin_id,       # J: MetinID
            st.session_state.hints,          # K: ToplamIpucu
            "Evet", "Evet", 0, 0            # L-O
        ]
        if save_to_sheets(row): st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.balloons(); st.success("Bugünkü çalışman kaydedildi!"); 
    if st.button("Yeni Metin"): st.session_state.phase = "setup"; st.rerun()
