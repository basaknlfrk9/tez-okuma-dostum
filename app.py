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
# OKUMA DOSTUM — ÖÖG DESTEKLİ NİHAİ VERİ KAYIT SİSTEMİ
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    p, li, div, span { line-height: 2.1 !important; word-spacing: 0.15em !important; }
    .stButton button { font-size: 20px !important; border-radius: 15px !important; padding: 12px !important; width: 100%; }
    .highlight-box { 
        background-color: #fcfcfc; padding: 30px; border-radius: 20px; 
        border: 2px solid #e0e0e0; font-size: 24px !important; margin-bottom: 20px; 
        white-space: pre-wrap; 
    }
    .card { border: 1px solid #ddd; border-radius: 15px; padding: 20px; background: white; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ Sheets Kayıt Fonksiyonu (A-O Sütun Garantili) ------------------
def save_performance_to_sheets(data_row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        
        # Sayfa ismini kontrol eder, yoksa ilk sekmeyi seçer
        try:
            ws = sh.worksheet("Performans")
        except:
            ws = sh.get_worksheet(0)
            
        ws.append_row(data_row)
        return True
    except Exception as e:
        st.error(f"⚠️ Tabloya Kayıt Yapılamadı! Hata: {str(e)}")
        return False

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

def tts_bytes(text: str) -> bytes:
    mp3_fp = BytesIO()
    gTTS(re.sub(r"[*#_]", "", text)[:1200], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

def get_ai_activity(source_text: str):
    system_prompt = """ÖÖG uzmanı bir öğretmensin. 
    1) 'sade_metin': Metnin ana yapısını koru, aşırı kısaltma yapma. Cümleleri basitleştir.
    2) JSON formatında 6 soru üret. Türler: 'bilgi', 'cikarim', 'ana_fikir', 'baslik', 'kelime'.
    Şema: {"sade_metin": "", "sorular": [{"kok": "", "A": "", "B": "", "C": "", "dogru": "A", "tur": "bilgi", "ipucu": ""}]}"""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": source_text}],
        response_format={ "type": "json_object" }
    )
    return json.loads(resp.choices[0].message.content)

# =========================================================
# OTURUM YÖNETİMİ
# =========================================================

if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# Çıkış Butonu
if st.session_state.phase != "auth":
    c_left, c_right = st.columns([8, 2])
    with c_right:
        if st.button("Çıkış Yap 🚪", key="logout"):
            st.session_state.clear()
            st.rerun()
    with c_left:
        st.caption(f"Öğrenci: {st.session_state.get('user')} | Sınıf: {st.session_state.get('sinif')}")

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    name = st.text_input("Adın:")
    grade = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
    if st.button("Sisteme Gir") and name:
        st.session_state.user = name
        st.session_state.sinif = grade
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = now_tr_str()
        st.session_state.phase = "setup"
        st.rerun()

# 2. KURULUM
elif st.session_state.phase == "setup":
    st.subheader("Okuma Metni Hazırla")
    metin_id = st.text_input("Metin Kimliği (Metin ID):", value="Metin_1")
    pdf_file = st.file_uploader("MEB PDF Yükle", type="pdf")
    text_input = st.text_area("Veya Metni Buraya Yapıştır")
    
    if st.button("Çalışmayı Başlat"):
        raw = text_input
        if pdf_file:
            raw = "\n".join([p.extract_text() for p in PdfReader(pdf_file).pages if p.extract_text()])
        
        if raw:
            with st.spinner("ÖÖG Materyali Hazırlanıyor..."):
                st.session_state.activity = get_ai_activity(raw)
                st.session_state.metin_id = metin_id
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
        if st.button("🔊 Sesli Dinle"):
            st.session_state.tts_count += 1
            st.audio(tts_bytes(act['sade_metin']))
    with c2:
        if st.button("✅ Okumayı Bitirdim"):
            st.session_state.phase = "questions"
            st.rerun()

# 4. SORULAR (Görsel 7/8 Sütun Sıralamasına Göre Kayıt)
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    q_idx = st.session_state.q_index

    if q_idx < len(sorular):
        q = sorular[q_idx]
        st.markdown(f"### Soru {q_idx + 1} / {len(sorular)}")
        st.markdown(f"<div class='card'>{q.get('kok')}</div>", unsafe_allow_html=True)
        
        cols = st.columns(3)
        for i, opt in enumerate(["A", "B", "C"]):
            with cols[i]:
                if st.button(f"{opt}) {q.get(opt)}", key=f"q_{q_idx}_{opt}"):
                    if opt == q.get('dogru'):
                        if q_idx not in st.session_state.correct_map:
                            st.session_state.correct_map[q_idx] = 1
                        
                        if q.get('tur') == 'ana_fikir': st.session_state.ana_fikir_dogru = True
                        if q.get('tur') == 'cikarim': st.session_state.cikarim_dogru = True
                        
                        st.success("🌟 Harika! Doğru.")
                        time.sleep(1.2)
                        st.session_state.q_index += 1
                        st.rerun()
                    else:
                        st.session_state.correct_map[q_idx] = 0
                        st.warning("Bu tam doğru değil. İpucuna bakıp tekrar dene! ✨")
        
        if st.button("💡 İpucu Al"):
            st.session_state.total_ipucu += 1
            st.info(f"Rehber Bilgi: {q.get('ipucu')}")
    else:
        # VERİLERİ HESAPLA VE TABLOYA (A-O) GÖNDER
        sure_dakika = round((time.time() - st.session_state.start_time_stamp) / 60, 2)
        dogru_s = sum(st.session_state.correct_map.values())
        yuzde = f"%{round((dogru_s / len(sorular)) * 100, 1)}"
        hatalar = [q.get('tur') for i, q in enumerate(sorular) if st.session_state.correct_map.get(i) == 0]
        
        # SÜTUN SIRALAMASI (A'dan O'ya):
        final_row = [
            st.session_state.session_id,     # A: OturumID
            st.session_state.user,          # B: Kullanici
            st.session_state.login_time,    # C: TarihSaat
            sure_dakika,                    # D: SureDakika
            st.session_state.sinif,         # E: SinifDuzeyi
            yuzde,                          # f: BasariYuzde
            len(sorular),                   # G: ToplamSoru
            dogru_s,                        # H: DogruSayi
            ", ".join(set(hatalar)) if hatalar else "Yok", # I: HataliKazanim
            st.session_state.metin_id,       # J: MetinID
            st.session_state.total_ipucu,   # K: ToplamIpucu
            "Evet" if st.session_state.ana_fikir_dogru else "Hayır", # L: AnaFikirDogru
            "Evet" if st.session_state.cikarim_dogru else "Hayır",   # M: CikarimDogru
            st.session_state.tts_count,      # N: TTS_Kullanim
            0                               # O: Mic_Kullanim
        ]
        
        if save_performance_to_sheets(final_row):
            st.session_state.phase = "done"
            st.rerun()

# 5. SONUÇ
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Mükemmel! Çalışman e-tabloya başarıyla kaydedildi.")
    if st.button("Yeni Metinle Başla"):
        st.session_state.phase = "setup"
        st.rerun()
