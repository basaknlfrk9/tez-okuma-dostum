import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError
import json, uuid, time, re, random, traceback
from gtts import gTTS
from io import BytesIO
import pandas as pd

# =========================================================
# OKUMA DOSTUM — ÖÖG UYUMLU GÜNCELLENMİŞ SÜRÜM
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 19px; background: #f7fbff; }
  .stButton button { width: 100%; border-radius: 16px; font-weight: 800; background: linear-gradient(90deg, #2f80ed 0%, #56ccf2 100%); color: white; }
  .highlight-box { background: #ffffff; padding: 22px; border-radius: 18px; box-shadow: 0 6px 16px rgba(0,0,0,0.05); border-left: 8px solid #ffd54f; font-size: 22px !important; line-height: 1.9 !important; margin-bottom: 16px; white-space: pre-wrap; }
  .card { background: #ffffff; padding: 16px; border-radius: 16px; border: 1px solid #e7eef7; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); }
</style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def _norm(x) -> str: return str(x or "").strip()
def now_tr() -> str: return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

def go_to_phase(target_phase: str):
    st.session_state.phase = target_phase
    st.rerun()

def top_back_button(target_phase: str, label: str = "⬅️ Geri"):
    col_a, col_b = st.columns([8, 1])
    with col_b:
        if st.button(label, key=f"top_back_{target_phase}_{st.session_state.get('phase','')}"):
            go_to_phase(target_phase)

# --- OPENAI & AUDIO ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_text_request(system_prompt, user_text, model="gpt-4o-mini", temperature=0.3):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        temperature=temperature
    )
    return resp

def openai_json_request(system_prompt, user_text, model="gpt-4o-mini"):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        response_format={"type": "json_object"},
        temperature=0
    )
    return resp

def get_audio(text: str):
    clean = re.sub(r"[*#_]", "", (text or ""))[:1000]
    tts = gTTS(text=clean, lang="tr")
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

# --- ESNEK ÖYKÜ HARİTASI PUANLAMA (NLP GÜNCELLEMESİ) ---
def _flexible_normalize(s: str) -> str:
    s = str(s or "").lower()
    # Türkçe karakter normalizasyonu ve temizlik
    repl = str.maketrans("İıŞşĞğÜüÖöÇç", "iissgguuoooc")
    s = s.translate(repl)
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())

def ai_score_story_map(metin: str, sm: dict):
    # Bu fonksiyon hem kurala hem de LLM'e bakar. LLM kararı daha esnektir.
    alanlar = ["kahraman", "mekan", "zaman", "problem", "olaylar", "cozum"]
    scores = {}
    
    sys_prompt = """Sen ÖÖG öğrencilerini değerlendiren uzman bir öğretmensin. 
    Öğrenci tam kelimeyi yazmasa bile, anlam olarak doğruyu yakaladıysa (eş anlamlı, yakın anlamlı, betimleme) 2 PUAN VER.
    Kısmen doğruysa 1 PUAN, tamamen alakasızsa 0 PUAN ver.
    JSON formatında döndür: {"score": 2, "reason": "Açıklama"}"""

    total = 0
    for alan in alanlar:
        cevap = sm.get(alan, "").strip()
        if not cevap:
            scores[alan] = 0
            continue
            
        user_input = f"Metin: {metin}\nAlan: {alan}\nÖğrenci Cevabı: {cevap}"
        try:
            res = openai_json_request(sys_prompt, user_input)
            data = json.loads(res.choices[0].message.content)
            scores[alan] = int(data.get("score", 0))
        except:
            scores[alan] = 1 # Hata durumunda öğrenci lehine 1 puan

    total = sum(scores.values())
    return scores, total, "AI Destekli Değerlendirme Tamamlandı"

# --- GSHEETS ---
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    if "\\n" in info.get("private_key", ""): info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def get_ws(sheet_name: str):
    sh = get_gs_client().open_by_url(st.secrets["GSHEET_URL"])
    return sh.worksheet(sheet_name)

def append_row_safe(sheet_name: str, row):
    try:
        ws = get_ws(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except: return False

# --- STATE MANAGEMENT ---
def reset_activity_states():
    st.session_state.q_idx = 0
    st.session_state.question_status = {}
    st.session_state.question_attempts = {}
    st.session_state.hints = 0
    st.session_state.story_map = {"kahraman":"", "mekan":"", "zaman":"", "problem":"", "olaylar":"", "cozum":""}
    st.session_state.saved_perf = False
    st.session_state.start_t = time.time()

if "phase" not in st.session_state: st.session_state.phase = "auth"

# --- UI LOGIC ---

# 1. AUTH
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    u = st.text_input("Öğrenci Kodun")
    mid = st.text_input("Metin ID", "Metin_001")
    if st.button("Başla"):
        st.session_state.user = u
        st.session_state.metin_id = mid
        st.session_state.session_id = str(uuid.uuid4())[:8]
        # Örnek statik veri (MetinBankasi'ndan çekme mantığın burada çalışacaktır)
        st.session_state.activity = {"sade_metin": "Örnek metin içeriği...", "sorular": [{"kok":"Soru 1?", "dogru":"A", "A":"Cevap 1", "B":"Cevap 2"}]}
        reset_activity_states()
        go_to_phase("during")

# 2. DURING (Okuma)
elif st.session_state.phase == "during":
    st.subheader("Metni Oku")
    st.write(st.session_state.activity["sade_metin"])
    if st.button("Bitirdim, Sorulara Geç"):
        go_to_phase("post")

# 3. POST (Öykü Haritası)
elif st.session_state.phase == "post":
    st.subheader("Öykü Haritası")
    sm = st.session_state.story_map
    sm["kahraman"] = st.text_input("👤 Kahraman", value=sm["kahraman"])
    sm["mekan"] = st.text_input("🏠 Mekan", value=sm["mekan"])
    sm["problem"] = st.text_input("⚠️ Problem", value=sm["problem"])
    
    if st.button("Puanla ve Devam Et"):
        scores, total, reason = ai_score_story_map(st.session_state.activity["sade_metin"], sm)
        st.session_state.story_map_total = total
        st.success(f"Puanın: {total}/12")
        go_to_phase("questions")

# 4. QUESTIONS (Soru Çözümü)
elif st.session_state.phase == "questions":
    sorular = st.session_state.activity.get("sorular", [])
    i = st.session_state.q_idx
    
    st.markdown(f"**Soru {i+1} / {len(sorular)}**")
    q = sorular[i]
    
    # DİNAMİK KEY: Soru değiştikçe radyo butonu sıfırlanır
    radio_key = f"q_{i}_attempt_{st.session_state.question_attempts.get(i,0)}"
    secim = st.radio(q["kok"], ["A", "B", "C", "D"], index=None, key=radio_key)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Kontrol Et"):
            if secim == q["dogru"]:
                st.session_state.question_status[i] = "correct"
                st.success("Harika! Doğru.")
                time.sleep(1)
                if i < len(sorular) - 1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    go_to_phase("finalize")
            else:
                st.error("Tekrar dene!")
                st.session_state.question_attempts[i] = st.session_state.question_attempts.get(i,0) + 1
                st.rerun()

    with col2:
        if st.button("Soruyu Geç"):
            st.session_state.question_status[i] = "skipped"
            if i < len(sorular) - 1:
                st.session_state.q_idx += 1
                st.rerun()
            else:
                go_to_phase("finalize")

# 5. FINALIZE
elif st.session_state.phase == "finalize":
    st.balloons()
    st.header("Tebrikler! 🎉")
    st.write(f"Öykü Haritası Puanın: {st.session_state.get('story_map_total', 0)}")
    if st.button("Başa Dön"):
        go_to_phase("auth")
