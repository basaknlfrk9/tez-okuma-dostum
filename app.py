import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re, json, uuid, time
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — HATA TESPİT VE KAYIT SİSTEMİ
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

# VERİ KAYDETME FONKSİYONU (HATA MESAJI GÖSTERİMLİ)
def save_data(row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        
        # Sayfa ismini bulmaya çalış, bulamazsa ilk sayfayı kullan
        try:
            ws = sh.worksheet("Performans")
        except:
            ws = sh.get_worksheet(0)
            
        ws.append_row(row)
        st.success("✅ Veri başarıyla e-tabloya eklendi!")
        return True
    except Exception as e:
        # BURASI ÇOK ÖNEMLİ: Hatayı ekrana basar
        st.error(f"❌ KAYIT HATASI: {str(e)}")
        return False

# AI ETKİNLİK ÜRETİMİ
def get_ai_content(text):
    prompt = "ÖÖG uzmanı olarak bu metni sadeleştir ve 6 soru (bilgi, cikarim, ana_fikir) üret. JSON formatında ver."
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        response_format={ "type": "json_object" }
    )
    return json.loads(resp.choices[0].message.content)

# --- UYGULAMA AKIŞI ---
if "phase" not in st.session_state: st.session_state.phase = "auth"

if st.session_state.phase == "auth":
    u = st.text_input("Adın:")
    s = st.selectbox("Sınıfın:", ["5","6","7","8"])
    if st.button("Giriş") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.login_time = now_tr_str()
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.phase = "setup"; st.rerun()

elif st.session_state.phase == "setup":
    txt = st.text_area("Metni Yapıştır")
    if st.button("Başlat") and txt:
        st.session_state.activity = get_ai_content(txt)
        st.session_state.phase = "read"
        st.session_state.q_idx = 0
        st.session_state.correct_map = {}
        st.session_state.start_time = time.time()
        st.rerun()

elif st.session_state.phase == "read":
    st.write(st.session_state.activity['sade_metin'])
    if st.button("Sorulara Geç"):
        st.session_state.phase = "questions"; st.rerun()

elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act['sorular']
    idx = st.session_state.q_idx
    
    if idx < len(sorular):
        q = sorular[idx]
        st.write(f"Soru {idx+1}: {q['kok']}")
        for o in ["A","B","C"]:
            if st.button(f"{o}) {q[o]}", key=f"{idx}_{o}"):
                st.session_state.correct_map[idx] = 1 if o == q['dogru'] else 0
                st.session_state.q_idx += 1; st.rerun()
    else:
        # KAYIT AŞAMASI
        dogru = sum(st.session_state.correct_map.values())
        sure = round((time.time() - st.session_state.start_time)/60, 2)
        
        # A'dan J'ye veri dizisi
        final_row = [
            st.session_state.session_id, # A
            st.session_state.user,       # B
            st.session_state.login_time, # C
            sure,                        # D
            st.session_state.sinif,      # E
            f"%{round(dogru/6*100)}",    # F
            6,                           # G
            dogru,                       # H
            "Analiz",                    # I
            "Metin_1"                    # J
        ]
        if save_data(final_row):
            st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.success("Bitti! Tabloyu kontrol et.")
    if st.button("Yeni Metin"): st.session_state.phase = "setup"; st.rerun()
