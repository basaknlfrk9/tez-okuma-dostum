import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re, json, uuid, time

# =========================================================
# OKUMA DOSTUM — NİHAİ KARARLI SÜRÜM
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide")

# Görsel Stil (ÖÖG Dostu)
st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    p, li, div, span { line-height: 2.1 !important; }
    .stButton button { font-size: 20px !important; border-radius: 15px !important; padding: 12px !important; }
    .highlight-box { background-color: #fcfcfc; padding: 30px; border-radius: 20px; border: 2px solid #e0e0e0; font-size: 24px !important; margin-bottom: 20px; white-space: pre-wrap; }
    .card { border: 1px solid #ddd; border-radius: 15px; padding: 20px; background: white; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# GÜVENLİ BAĞLANTI (Secrets Kontrolü)
def get_ai_client():
    try:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception as e:
        st.error("OpenAI Anahtarı Bulunamadı. Lütfen Secrets ayarlarını kontrol edin.")
        st.stop()

client = get_ai_client()

def save_to_sheets(row_data):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        try:
            ws = sh.worksheet("Performans")
        except:
            ws = sh.get_worksheet(0)
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"Tablo Kayıt Hatası: {e}")
        return False

# OTURUM BAŞLATMA
if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# 1. GİRİŞ EKRANI
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    name = st.text_input("Adın:")
    grade = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])
    if st.button("Giriş Yap") and name:
        st.session_state.user = name
        st.session_state.sinif = grade
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
        st.session_state.phase = "setup"
        st.rerun()

# 2. KURULUM (METİN YÜKLEME)
elif st.session_state.phase == "setup":
    st.subheader("Okuma Metnini Hazırla")
    m_id = st.text_input("Metin ID:", value="Metin_1")
    up = st.file_uploader("PDF Yükle", type="pdf")
    txt = st.text_area("Veya Metni Yapıştır")
    
    if st.button("Çalışmayı Başlat"):
        raw = txt
        if up:
            raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        
        if raw:
            with st.spinner("Yapay Zeka Metni İşliyor..."):
                try:
                    prompt = "ÖÖG uzmanı olarak metni sadeleştir ve 6 soru içeren saf JSON üret. Şema: {'sade_metin': '...', 'sorular': [{'kok': '...', 'A': '...', 'B': '...', 'C': '...', 'dogru': 'A', 'tur': 'bilgi', 'ipucu': '...'}]}"
                    resp = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw}],
                        response_format={ "type": "json_object" }
                    )
                    st.session_state.activity = json.loads(resp.choices[0].message.content)
                    st.session_state.metin_id = m_id
                    st.session_state.phase = "read"
                    st.session_state.q_idx = 0
                    st.session_state.correct_map = {}
                    st.session_state.total_ipucu = 0
                    st.session_state.start_time = time.time()
                    st.rerun()
                except Exception as e:
                    st.error(f"Yapay zeka yanıtı işlenemedi: {e}")

# 3. OKUMA AŞAMASI (Hata Veren Satır Düzeltildi)
elif st.session_state.phase == "read":
    # KeyError koruması: get() kullanarak anahtar yoksa boş metin göster
    metin = st.session_state.activity.get('sade_metin', "Metin yüklenirken bir hata oluştu.")
    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)
    
    if st.button("✅ Okudum, Sorulara Geç"):
        st.session_state.phase = "questions"
        st.rerun()

# 4. SORULAR AŞAMASI
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    idx = st.session_state.q_idx

    if idx < len(sorular):
        q = sorular[idx]
        st.markdown(f"### Soru {idx + 1}")
        st.write(q.get('kok', 'Soru metni bulunamadı.'))
        
        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt)}", key=f"q_{idx}_{opt}"):
                if opt == q.get('dogru'):
                    if idx not in st.session_state.correct_map: st.session_state.correct_map[idx] = 1
                    st.success("Harika! Doğru cevap.")
                    time.sleep(1)
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.session_state.correct_map[idx] = 0
                    st.warning("Tekrar dene! İpucu butonuna basabilirsin.")
        
        if st.button("💡 İpucu"):
            st.session_state.total_ipucu += 1
            st.info(q.get('ipucu', 'Metne tekrar göz atabilirsin.'))
    else:
        # VERİ KAYIT
        dogru = sum(st.session_state.correct_map.values())
        dakika = round((time.time() - st.session_state.start_time)/60, 2)
        
        final_row = [
            st.session_state.session_id,     # A: OturumID
            st.session_state.user,          # B: Kullanici
            st.session_state.login_time,    # C: TarihSaat
            dakika,                         # D: SureDakika
            st.session_state.sinif,         # E: SinifDuzeyi
            f"%{round(dogru/6*100, 1)}",    # F: BasariYuzde
            len(sorular),                   # G: ToplamSoru
            dogru,                          # H: DogruSayi
            "Analiz",                       # I: HataliKazanim
            st.session_state.metin_id,       # J: MetinID
            st.session_state.total_ipucu,   # K: ToplamIpucu
            "-", "-", 0, 0                  # L-O
        ]
        if save_to_sheets(final_row):
            st.session_state.phase = "done"
            st.rerun()

elif st.session_state.phase == "done":
    st.balloons()
    st.success("Tebrikler! Veriler başarıyla kaydedildi.")
    if st.button("Yeni Metne Başla"):
        st.session_state.phase = "setup"
        st.rerun()
    if st.button("Çıkış"):
        st.session_state.clear()
        st.rerun()
