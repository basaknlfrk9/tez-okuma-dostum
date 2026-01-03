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
# OKUMA DOSTUM — NİHAİ PEDAGOJİK VE TEKNİK DÜZENLEME
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
    gTTS(re.sub(r"[*#_]", "", text)[:1200], lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

def get_ai_activity(source_text: str):
    # Metni çok kısaltmaması için prompt özelleştirildi
    system_prompt = """ÖÖG uzmanı bir öğretmensin. 
    1) 'sade_metin': Kaynak metnin ana yapısını ve uzunluğunu koru, sadece karmaşık cümleleri basitleştir.
    2) JSON formatında 6 farklı soru üret. 
    Şema: {"sade_metin": "", "sorular": [{"kok": "", "A": "", "B": "", "C": "", "dogru": "A", "tur": "bilgi", "ipucu": ""}]}"""
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
    
    # Görseldeki (7.jpg) sütun düzenine tam uyumlu satır verisi
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
        "Evet" if st.session_state.ana_fikir_dogru else "Hayır", # L: AnaFikirDogruM
        "Evet" if st.session_state.cikarim_dogru else "Hayır",   # M: CikarimDogruMu
        st.session_state.tts_count,      # N: TTS_Kullanim
        0                               # O: Mic_Kullanim
    ]
    perf_sheet.append_row(row)

# =========================================================
# AKIŞ YÖNETİMİ
# =========================================================

if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# Çıkış Butonu (Global)
if st.session_state.phase != "auth":
    col_l, col_r = st.columns([8, 2])
    with col_r:
        if st.button("Çıkış Yap 🚪"):
            st.session_state.clear()
            st.rerun()
    with col_l:
        st.caption(f"Aktif Oturum: {st.session_state.get('user')} | {st.session_state.get('sinif')}. Sınıf")

# 1. GİRİŞ
if st.session_state.phase == "auth":
    st.title("📚 Okuma Dostum")
    u = st.text_input("Öğrenci Adı:")
    s = st.selectbox("Sınıf Düzeyi:", ["5", "6", "7", "8"])
    if st.button("Sisteme Giriş") and u:
        st.session_state.user, st.session_state.sinif = u, s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = now_tr_str()
        st.session_state.phase = "setup"
        st.rerun()

# 2. HAZIRLIK
elif st.session_state.phase == "setup":
    st.subheader("Okuma Metni Yükleme")
    m_id = st.text_input("Metin Kimliği (ID):", value="Metin_1")
    up = st.file_uploader("PDF Metni Seçin", type="pdf")
    txt = st.text_area("Veya Metni Buraya Yapıştırın")
    if st.button("Çalışmayı Başlat"):
        raw = txt
        if up:
            raw = "\n".join([p.extract_text() for p in PdfReader(up).pages if p.extract_text()])
        if raw:
            with st.spinner("Yapay Zeka Metni Hazırlıyor..."):
                st.session_state.activity = get_ai_activity(raw)
                st.session_state.metin_id = m_id
                st.session_state.phase = "read"; st.session_state.q_index = 0
                st.session_state.correct_map = {}; st.session_state.total_ipucu = 0
                st.session_state.tts_count = 0
                st.session_state.ana_fikir_dogru = False; st.session_state.cikarim_dogru = False
                st.session_state.start_time_stamp = time.time()
                st.rerun()

# 3. OKUMA
elif st.session_state.phase == "read":
    act = st.session_state.activity
    st.markdown(f"<div class='highlight-box'>{act['sade_metin']}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔊 Metni Sesli Dinle"):
            st.session_state.tts_count += 1
            st.audio(tts_bytes(act['sade_metin']))
    with c2:
        if st.button("✅ Okudum, Sorulara Geç"):
            st.session_state.phase = "questions"; st.rerun()

# 4. SORULAR (Yönlendirici Geri Bildirim Sistemi)
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get('sorular', [])
    curr = st.session_state.q_index

    if curr < len(sorular):
        q = sorular[curr]
        st.markdown(f"### Soru {curr + 1} / {len(sorular)}")
        st.markdown(f"<div class='card'>{q.get('kok')}</div>", unsafe_allow_html=True)
        
        colA, colB, colC = st.columns(3)
        # Her buton için mantık
        for i, opt in enumerate(["A", "B", "C"]):
            with [colA, colB, colC][i]:
                if st.button(f"{opt}) {q.get(opt)}", key=f"btn_{curr}_{opt}"):
                    if opt == q.get('dogru'):
                        st.session_state.correct_map[curr] = 1
                        if q.get('tur') == 'ana_fikir': st.session_state.ana_fikir_dogru = True
                        if q.get('tur') == 'cikarim': st.session_state.cikarim_dogru = True
                        st.success("🌟 Harika! Doğru cevabı buldun.")
                        time.sleep(1.5)
                        st.session_state.q_index += 1
                        st.rerun()
                    else:
                        st.session_state.correct_map[curr] = 0
                        st.warning("Bu cevap tam uymadı. İpucunu oku ve tekrar dene! ✨")
        
        if st.button("💡 İpucu Yardımı Al"):
            st.session_state.total_ipucu += 1
            st.info(f"Yol Gösterici İpucu: {q.get('ipucu')}")
    else:
        performans_kaydet()
        st.session_state.phase = "done"; st.rerun()

# 5. SONUÇ
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Çalışma başarıyla tamamlandı ve kaydedildi!")
    if st.button("Yeni Bir Metne Başla"):
        st.session_state.phase = "setup"; st.rerun()
