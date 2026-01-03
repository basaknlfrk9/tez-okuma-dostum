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
# OKUMA DOSTUM — VERİ KAYIT GARANTİLİ SİSTEM
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

# ------------------ Sheets Bağlantısı (Hata Korumalı) ------------------
def save_to_sheets(data_row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        ws = sh.worksheet("Performans")
        ws.append_row(data_row)
        return True
    except Exception as e:
        st.error(f"Tabloya yazılırken hata oluştu: {e}")
        return False

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

def tts_bytes(text: str) -> bytes:
    mp3_fp = BytesIO()
    gTTS(re.sub(r"[*#_]", "", text)[:1200], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

def get_ai_activity(source_text: str):
    system_prompt = """ÖÖG uzmanı bir öğretmensin. 
    1) 'sade_metin': Metni orta uzunlukta tut, sadece karmaşık yapıları sadeleştir.
    2) JSON formatında 6 farklı soru üret. 
    Şema: {"sade_metin": "", "sorular": [{"kok": "", "A": "", "B": "", "C": "", "dogru": "A", "tur": "bilgi", "ipucu": ""}]}"""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": source_text}],
        response_format={ "type": "json_object" }
    )
    return json.loads(resp.choices[0].message.content)

# =========================================================
# AKIŞ VE KONTROLLER
# =========================================================

if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# Çıkış Butonu
if st.session_state.phase != "auth":
    col_info, col_logout = st.columns([8, 2])
    with col_logout:
        if st.button("Çıkış Yap 🚪"):
            st.session_state.clear()
            st.rerun()
    with col_info:
        st.caption(f"👤 {st.session_state.get('user')} | 🎓 {st.session_state.get('sinif')}. Sınıf")

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    u = st.text_input("Adın:")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
    if st.button("Giriş Yap") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = now_tr_str()
        st.session_state.phase = "setup"
        st.rerun()

# 2. KURULUM
elif st.session_state.phase == "setup":
    st.subheader("Metni Hazırla")
    m_id = st.text_input("Metin ID:", value="Metin_1")
    up = st.file_uploader("PDF Yükle", type="pdf")
    txt = st.text_area("Veya Metin Yapıştır")
    if st.button("Çalışmayı Başlat"):
        raw = txt
        if up:
            raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        if raw:
            with st.spinner("Hazırlanıyor..."):
                st.session_state.activity = get_ai_activity(raw)
                st.session_state.metin_id = m_id
                st.session_state.phase = "read"
                st.session_state.q_index = 0
                st.session_state.correct_map = {}
                st.session_state.total_ipucu = 0
                st.session_state.tts_count = 0
                st.session_state.ana_fikir_dogru = False
                st.session_state.cikarim_dogru = False
                st.session_state.start_time_stamp = time.time()
                st.rerun()

# 3. OKUMA
elif st.session_state.phase == "read":
    act = st.session_state.activity
    st.markdown(f"<div class='highlight-box'>{act['sade_metin']}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔊 Metni Dinle"):
            st.session_state.tts_count += 1
            st.audio(tts_bytes(act['sade_metin']))
    with c2:
        if st.button("✅ Okumayı Bitirdim"):
            st.session_state.phase = "questions"
            st.rerun()

# 4. SORULAR
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    curr_idx = st.session_state.q_index

    if curr_idx < len(sorular):
        q = sorular[curr_idx]
        st.markdown(f"### Soru {curr_idx + 1} / {len(sorular)}")
        st.markdown(f"<div class='card'>{q.get('kok')}</div>", unsafe_allow_html=True)
        
        colA, colB, colC = st.columns(3)
        for i, opt in enumerate(["A", "B", "C"]):
            with [colA, colB, colC][i]:
                if st.button(f"{opt}) {q.get(opt)}", key=f"q_{curr_idx}_{opt}"):
                    if opt == q.get('dogru'):
                        if curr_idx not in st.session_state.correct_map: # İlk seferde mi bildi?
                            st.session_state.correct_map[curr_idx] = 1
                        
                        if q.get('tur') == 'ana_fikir': st.session_state.ana_fikir_dogru = True
                        if q.get('tur') == 'cikarim': st.session_state.cikarim_dogru = True
                        
                        st.success("🌟 Doğru!")
                        time.sleep(1.2)
                        st.session_state.q_index += 1
                        st.rerun()
                    else:
                        st.session_state.correct_map[curr_idx] = 0 # Yanlış deneme
                        st.warning("Tekrar dene! İpucu butonuna basabilirsin.")
        
        if st.button("💡 İpucu"):
            st.session_state.total_ipucu += 1
            st.info(q.get('ipucu'))
    else:
        # VERİLERİ TOPLA VE KAYDET
        sure_saniye = time.time() - st.session_state.start_time_stamp
        dakika = round(sure_saniye / 60, 2)
        dogru_sayisi = sum(st.session_state.correct_map.values())
        yuzde = f"%{round((dogru_sayisi / len(sorular)) * 100, 1)}"
        hatalar = [q.get('tur') for i, q in enumerate(sorular) if st.session_state.correct_map.get(i) == 0]
        
        final_row = [
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
            0                               # O: Mic_Kullanim
        ]
        
        if save_to_sheets(final_row):
            st.session_state.phase = "done"
            st.rerun()

# 5. BİTİŞ
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Tebrikler! Tüm veriler başarıyla kaydedildi.")
    if st.button("Yeni Metinle Başla"):
        st.session_state.phase = "setup"
        st.rerun()
