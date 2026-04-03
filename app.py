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
# OKUMA DOSTUM — ÖÖG UYUMLU TAM SÜRÜM (GÜNCELLENMİŞ)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 19px; background: #f7fbff; }
  .stButton button { width: 100%; border-radius: 16px; height: 3em; font-weight: 800; background: linear-gradient(90deg, #2f80ed 0%, #56ccf2 100%); color: white; }
  .highlight-box { background: #ffffff; padding: 22px; border-radius: 18px; box-shadow: 0 6px 16px rgba(0,0,0,0.05); border-left: 8px solid #ffd54f; font-size: 22px !important; line-height: 1.9 !important; margin-bottom: 16px; white-space: pre-wrap; }
  .card { background: #ffffff; padding: 16px; border-radius: 16px; border: 1px solid #e7eef7; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
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

# =========================================================
# OPENAI & AI LOGIC
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_json_request(system_prompt, user_text, model="gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        response_format={"type": "json_object"},
        temperature=0
    )

def openai_text_request(system_prompt, user_text, model="gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        temperature=0.3
    )

# --- ESNEK ÖYKÜ HARİTASI PUANLAMA (EŞ ANLAMLI DESTEĞİ) ---
def ai_score_story_map(metin: str, sm: dict):
    alanlar = ["kahraman", "mekan", "zaman", "problem", "olaylar", "cozum"]
    sys_prompt = """Sen ÖÖG (Özel Öğrenme Güçlüğü) uzmanı bir öğretmensin. 
    Öğrencinin öykü haritası cevaplarını metne göre değerlendir.
    KRİTER: Öğrenci tam kelimeyi yazmasa bile, anlam olarak (eş anlamlı, yakın anlamlı, açıklayıcı ifade) doğruyu yakaladıysa 2 PUAN ver.
    Kısmen doğruysa 1 PUAN, alakasızsa 0 PUAN ver.
    Sadece şu JSON formatında cevap ver: {"scores": {"kahraman": 2, ...}, "reason": "Kısa genel özet"}"""
    
    user_payload = f"Metin: {metin}\nÖğrenci Cevapları: {json.dumps(sm, ensure_ascii=False)}"
    try:
        resp = openai_json_request(sys_prompt, user_payload)
        data = json.loads(resp.choices[0].message.content)
        scores = data.get("scores", {k: 0 for k in alanlar})
        total = sum(scores.values())
        return scores, total, data.get("reason", "Değerlendirildi.")
    except:
        return {k: 1 for k in alanlar}, 6, "AI şu an puanlayamadı, varsayılan puan verildi."

# =========================================================
# GOOGLE SHEETS
# =========================================================
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    if "\\n" in info.get("private_key", ""): info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def get_ws(sheet_name: str):
    sh = get_gs_client().open_by_url(st.secrets["GSHEET_URL"])
    return sh.worksheet(sheet_name)

def read_sheet_records(sheet_name: str):
    ws = get_ws(sheet_name)
    return ws.get_all_records()

def append_row_safe(sheet_name: str, row):
    try:
        ws = get_ws(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except: return False

def save_reading_process(kayit_turu: str, icerik: str, paragraf_no=None):
    row = [st.session_state.get("session_id", ""), st.session_state.get("user", ""), now_tr(), "", st.session_state.get("metin_id", ""), paragraf_no or "", kayit_turu, (icerik or "")[:45000]]
    append_row_safe("OkumaSüreci", row)

# =========================================================
# METİN & SORU YÜKLEME
# =========================================================
def list_metin_ids():
    try:
        rows = read_sheet_records("MetinBankasi")
        return sorted(list(set([_norm(r.get("metin_id")) for r in rows if r.get("metin_id")])))
    except: return ["Metin_001"]

def load_activity_from_bank(metin_id: str):
    try:
        mrows = read_sheet_records("MetinBankasi")
        match_m = [r for r in mrows if _norm(r.get("metin_id")) == metin_id]
        if not match_m: return None, "Metin bulunamadı."
        
        qrows = read_sheet_records("SoruBankasi")
        match_q = [r for r in qrows if _norm(r.get("metin_id")) == metin_id]
        
        sorular = []
        for r in match_q:
            sorular.append({
                "kok": r.get("kok", ""), "dogru": str(r.get("dogru", "")).upper(),
                "A": r.get("A", ""), "B": r.get("B", ""), "C": r.get("C", ""), "D": r.get("D", "")
            })
        
        return {
            "sade_metin": match_m[0].get("metin", ""),
            "baslik": match_m[0].get("baslik", ""),
            "pre_ipucu": match_m[0].get("pre_ipucu", ""),
            "sorular": sorular,
            "opts": ["A", "B", "C", "D"]
        }, ""
    except Exception as e: return None, str(e)

def split_paragraphs(text: str):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paras if paras else [text]

# =========================================================
# STATE RESET
# =========================================================
def reset_activity_states():
    st.session_state.q_idx = 0
    st.session_state.question_status = {}
    st.session_state.question_attempts = {}
    st.session_state.hints = 0
    st.session_state.story_map = {"kahraman":"", "mekan":"", "zaman":"", "problem":"", "olaylar":"", "cozum":""}
    st.session_state.saved_perf = False
    st.session_state.p_idx = 0
    st.session_state.start_t = time.time()
    st.session_state.prediction = ""
    st.session_state.reading_speed = ""
    st.session_state.final_important_note = ""
    st.session_state.prior_knowledge = ""
    st.session_state.summary = ""

# =========================================================
# ANA AKIŞ (PHASES)
# =========================================================
if "phase" not in st.session_state: st.session_state.phase = "auth"

# --- 1) AUTH ---
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    u = st.text_input("Öğrenci Kodun")
    metin_listesi = list_metin_ids()
    selected_id = st.selectbox("Metin Seç", metin_listesi)
    
    if st.button("Başlayalım"):
        if u and selected_id:
            st.session_state.user = u
            st.session_state.metin_id = selected_id
            st.session_state.session_id = str(uuid.uuid4())[:8]
            activity, err = load_activity_from_bank(selected_id)
            if activity:
                st.session_state.activity = activity
                st.session_state.paragraphs = split_paragraphs(activity["sade_metin"])
                reset_activity_states()
                go_to_phase("pre")
            else: st.error(err)

# --- 2) PRE ---
elif st.session_state.phase == "pre":
    st.subheader("Okuma Öncesi")
    st.info(f"Başlık: {st.session_state.activity.get('baslik')}")
    st.session_state.prediction = st.text_input("Sence bu metin ne hakkında?", value=st.session_state.prediction)
    st.session_state.reading_speed = st.radio("Okuma Hızın?", ["Yavaş", "Orta", "Hızlı"], index=None)
    if st.button("Metne Geç"):
        if st.session_state.reading_speed: go_to_phase("during")
        else: st.warning("Hız seçmelisin.")

# --- 3) DURING ---
elif st.session_state.phase == "during":
    p_idx = st.session_state.p_idx
    paras = st.session_state.paragraphs
    st.subheader(f"Bölüm {p_idx+1} / {len(paras)}")
    st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Geri", disabled=(p_idx==0)): 
            st.session_state.p_idx -= 1
            st.rerun()
    with c2:
        if p_idx < len(paras) - 1:
            if st.button("İleri ➡️"):
                st.session_state.p_idx += 1
                st.rerun()
        else:
            if st.button("Okumayı Bitir"): go_to_phase("post")

# --- 4) POST (ÖYKÜ HARİTASI) ---
elif st.session_state.phase == "post":
    st.subheader("Öykü Haritası")
    sm = st.session_state.story_map
    sm["kahraman"] = st.text_input("👤 Kahraman", value=sm["kahraman"])
    sm["mekan"] = st.text_input("🏠 Mekan", value=sm["mekan"])
    sm["problem"] = st.text_input("⚠️ Problem", value=sm["problem"])
    sm["olaylar"] = st.text_area("🔁 Olaylar", value=sm["olaylar"])
    sm["cozum"] = st.text_input("✅ Çözüm", value=sm["cozum"])
    
    if st.button("Puanla ve Sorulara Geç"):
        with st.spinner("AI Puanlıyor..."):
            scores, total, reason = ai_score_story_map(st.session_state.activity["sade_metin"], sm)
            st.session_state.story_map_total = total
            st.session_state.story_map_scores = scores
            save_reading_process("STORY_MAP_SCORED", f"Puan: {total}/12")
            st.success(f"Puanın: {total}/12. Harika!")
            time.sleep(2)
            go_to_phase("questions")

# --- 5) QUESTIONS ---
elif st.session_state.phase == "questions":
    sorular = st.session_state.activity["sorular"]
    i = st.session_state.q_idx
    q = sorular[i]
    
    st.subheader(f"Soru {i+1} / {len(sorular)}")
    st.markdown(f"<div class='card'>{q['kok']}</div>", unsafe_allow_html=True)
    
    # RADYO BUTONU RESETLEME İÇİN DİNAMİK KEY
    r_key = f"q_{i}_at_{st.session_state.question_attempts.get(i,0)}"
    secim = st.radio("Cevabın:", ["A", "B", "C", "D"], index=None, key=r_key, format_func=lambda x: f"{x}: {q.get(x)}")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Kontrol Et"):
            if secim == q["dogru"]:
                st.session_state.question_status[i] = "correct"
                save_reading_process("Q_CORRECT", f"Soru {i+1}")
                if i < len(sorular) - 1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else: go_to_phase("finalize")
            else:
                st.error("Tekrar dene!")
                st.session_state.question_attempts[i] = st.session_state.question_attempts.get(i,0) + 1
                st.rerun()
    with c2:
        if st.button("Soruyu Geç"):
            st.session_state.question_status[i] = "skipped"
            save_reading_process("Q_SKIPPED", f"Soru {i+1}")
            if i < len(sorular) - 1:
                st.session_state.q_idx += 1
                st.rerun()
            else: go_to_phase("finalize")

# --- 6) FINALIZE ---
elif st.session_state.phase == "finalize":
    st.balloons()
    st.header("Çalışma Bitti! 🎉")
    dogru = sum(1 for v in st.session_state.question_status.values() if v == "correct")
    st.write(f"Doğru Sayın: {dogru} / {len(st.session_state.activity['sorular'])}")
    st.write(f"Öykü Haritası Puanın: {st.session_state.get('story_map_total', 0)} / 12")
    
    if st.button("Başa Dön"):
        st.session_state.clear()
        st.rerun()
