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
# OKUMA DOSTUM — ÖÖG & GELİŞİM TAKİP (GÜNCEL SÜTUN DÜZENİ)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    p, li, div, span { line-height: 2.1 !important; }
    .stButton button { font-size: 20px !important; border-radius: 15px !important; padding: 12px !important; width: 100%; }
    .highlight-box { background-color: #fcfcfc; padding: 30px; border-radius: 20px; border: 2px solid #e0e0e0; font-size: 24px !important; margin-bottom: 20px; white-space: pre-wrap; }
    .card { border: 1px solid #ddd; border-radius: 15px; padding: 20px; background: white; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def get_perf_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
    gc = gspread.authorize(credentials)
    workbook = gc.open_by_url(st.secrets["GSHEET_URL"])
    return workbook.worksheet("Performans")

perf_sheet = get_perf_sheet()

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

def tts_bytes(text: str) -> bytes:
    mp3_fp = BytesIO()
    gTTS(re.sub(r"[*#_]", "", text)[:1000], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

def get_ai_activity(source_text: str):
    system_prompt = """ÖÖG uzmanı bir öğretmensin. JSON formatında 6 soru üret. 
    JSON şeması: {"sade_metin": "", "sorular": [{"kok": "", "A": "", "B": "", "C": "", "dogru": "A", "tur": "bilgi", "ipucu": ""}]}"""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": source_text}],
        response_format={ "type": "json_object" }
    )
    return json.loads(resp.choices[0].message.content)

def performans_kaydet():
    sure_saniye = time.time() - st.session_state.start_time_stamp
    dakika = round(sure_saniye / 60, 2)
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    dogru_sayisi = sum(st.session_state.correct_map.values())
    yuzde = f"%{round((dogru_sayisi / len(sorular)) * 100, 1)}" if sorular else "%0"
    
    hatalar = [q.get('tur') for i, q in enumerate(sorular) if st.session_state.correct_map.get(i) == 0]
    
    # 7.jpg görselindeki sütun sırasına (A-O) tam uyum:
    row = [
        st.session_state.session_id,     # A: OturumID
        st.session_state.user,          # B: Kullanici
        st.session_state.login_time,    # C: TarihSaat
        dakika,                         # D: SureDakika
        st.session_state.sinif,         # E: SinifDuzeyi
        yuzde,                          # F: BasariYuzde
        len(sorular),                   # G: ToplamSoru
        dogru_sayisi,                   # H: DogruSayi
        ", ".join(set(hatalar)) if hatalar else "Yok", # I: HataliKazanim
        st.session_state.metin_id,       # J: MetinID
        st.session_state.total_ipucu,   # K: ToplamIpucu
        "Evet" if st.session_state.ana_fikir_dogru else "Hayır", # L: AnaFikirDogru
        "Evet" if st.session_state.cikarim_dogru else "Hayır",   # M: CikarimDogru
        st.session_state.tts_count,      # N: TTS_Kullanim
        0                               # O: Mic_Kullanim (Varsayılan 0)
    ]
    perf_sheet.append_row(row)

# =========================================================
# AKIŞ
# =========================================================

if "phase" not in st.session_state:
    st.session_state.phase = "auth"

if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    u = st.text_input("Adın:")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
    if st.button("Giriş") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = now_tr_str()
        st.session_state.phase = "setup"
        st.rerun()

elif st.session_state.phase == "setup":
    m_id = st.text_input("Metin ID:", value="Metin_1")
    up = st.file_uploader("PDF Yükle", type="pdf")
    txt = st.text_area("Veya Metin Yapıştır")
    if st.button("Başlat"):
        raw = txt
        if up:
            raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        if raw:
            with st.spinner("Hazırlanıyor..."):
                st.session_state.activity = get_ai_activity(raw)
                st.session_state.metin_id = m_id
                st.session_state.phase = "read"; st.session_state.q_index = 0
                st.session_state.correct_map = {}; st.session_state.total_ipucu = 0
                st.session_state.tts_count = 0
                st.session_state.ana_fikir_dogru = False; st.session_state.cikarim_dogru = False
                st.session_state.start_time_stamp = time.time()
                st.rerun()

elif st.session_state.phase == "read":
    act = st.session_state.activity
    st.markdown(f"<div class='highlight-box'>{act['sade_metin']}</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔊 Dinle"):
            st.session_state.tts_count += 1
            st.audio(tts_bytes(act['sade_metin']))
    with col2:
        if st.button("✅ Sorulara Geç"):
            st.session_state.phase = "questions"; st.rerun()

elif st.session_state.phase == "questions":
    act = st.session_state.activity
    idx = st.session_state.q_index
    sorular = act.get('sorular', [])
    if idx < len(sorular):
        q = sorular[idx]
        st.markdown(f"### Soru {idx+1}")
        st.markdown(f"<div class='card'>{q.get('kok','Soru bulunamadı')}</div>", unsafe_allow_html=True)
        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt)}", key=f"q_{idx}_{opt}"):
                is_correct = (opt == q.get('dogru'))
                st.session_state.correct_map[idx] = 1 if is_correct else 0
                
                # Kazanım Analizi (L ve M sütunları için)
                if is_correct:
                    if q.get('tur') == 'ana_fikir': st.session_state.ana_fikir_dogru = True
                    if q.get('tur') == 'cikarim': st.session_state.cikarim_dogru = True
                    st.success("🌟 Tebrikler! Doğru.")
                else:
                    st.error(f"❌ Yanlış. Doğru cevap: {q.get('dogru')}")
                
                time.sleep(2)
                st.session_state.q_index += 1
                st.rerun()
        if st.button("💡 İpucu"):
            st.session_state.total_ipucu += 1
            st.info(q.get('ipucu', 'Metne bak!'))
    else:
        performans_kaydet()
        st.session_state.phase = "done"; st.rerun()

elif st.session_state.phase == "done":
    st.balloons(); st.success("Tamamlandı! Veriler tabloya işlendi.")
    if st.button("Yeni Metin"):
        st.session_state.phase = "setup"; st.rerun()
