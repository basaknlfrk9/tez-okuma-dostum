import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import json, uuid, time, re, traceback
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — ÖÖG DESTEKLİ & AKILLI REHBER SİSTEMİ
# =========================================================
st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ---------- Tasarım ----------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
  html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 20px; }
  .stButton button {
    width: 100%;
    border-radius: 18px;
    height: 3.0em;
    font-weight: 600;
    font-size: 20px !important;
    border: 2px solid #eee;
    background-color: #3498db;
    color: white;
  }
  .highlight-box {
    background-color: #ffffff;
    padding: 26px;
    border-radius: 22px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.08);
    border-left: 12px solid #f1c40f;
    font-size: 22px !important;
    line-height: 1.9 !important;
    margin-bottom: 18px;
  }
  .small-note { color:#666; font-size:16px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# OPENAI
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =========================================================
# GOOGLE SHEETS (STABİL + SEKME ADI ESNEK)
# =========================================================
@st.cache_resource
def get_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    info = dict(st.secrets["GSHEETS"])
    pk = info.get("private_key", "")
    if isinstance(pk, str) and "\\n" in pk:
        info["private_key"] = pk.replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    gc = get_client()
    return gc.open_by_url(st.secrets["GSHEET_URL"])

def get_ws(sheet_name: str):
    sh = get_spreadsheet()
    wanted = sheet_name.strip().lower()
    for w in sh.worksheets():
        if w.title.strip().lower() == wanted:
            return w
    raise ValueError(f"Sheet sekmesi bulunamadı: '{sheet_name}'. Mevcut: {[w.title for w in sh.worksheets()]}")

def save_to_sheets(row, sheet_name="Performans"):
    try:
        ws = get_ws(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        st.error(f"❌ Veri Kayıt Hatası ({sheet_name}) (tam):")
        st.code(traceback.format_exc())
        return False

# =========================================================
# SOHBET LOG (Sohbet sekmesine)
# =========================================================
def log_chat(event, payload):
    """
    Sohbet sekmesi şema:
    A session_id
    B user
    C timestamp
    D phase/event
    E payload (json/text)
    """
    try:
        ts = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")
        row = [
            st.session_state.get("session_id", ""),
            st.session_state.get("user", ""),
            ts,
            event,
            payload[:45000] if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)[:45000]
        ]
        save_to_sheets(row, sheet_name="Sohbet")
    except Exception:
        # sohbet logu bozulsa bile uygulamayı düşürmeyelim
        pass

# =========================================================
# SES (Dinle)
# =========================================================
def get_audio(text):
    clean = re.sub(r"[*#_]", "", text)[:1000]
    tts = gTTS(text=clean, lang="tr")
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

# =========================================================
# SESSION STATE
# =========================================================
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "saved_perf" not in st.session_state: st.session_state.saved_perf = False
if "login_logged" not in st.session_state: st.session_state.login_logged = False

# Global çıkış (auth dışında)
if st.session_state.phase != "auth":
    col_a, col_b = st.columns([9, 1])
    with col_b:
        if st.button("Çıkış 🚪"):
            # çıkış logla
            try:
                log_chat("LOGOUT", "user_logout_clicked")
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()

# =========================================================
# 1) GİRİŞ
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Adın Soyadın:")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])

    if st.button("Hadi Başlayalım! 🚀") and u:
        st.session_state.user = u
        st.session_state.sinif = s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

        st.session_state.chat_history = []
        st.session_state.saved_perf = False
        st.session_state.login_logged = False

        # ✅ Giriş logu: Sohbet sekmesine kesin yaz
        if not st.session_state.login_logged:
            log_chat("LOGIN", json.dumps({
                "sinif": s,
                "login_time": st.session_state.login_time
            }, ensure_ascii=False))
            st.session_state.login_logged = True

        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) KURULUM
# =========================================================
elif st.session_state.phase == "setup":
    st.subheader("📄 Okuyacağımız Metni Hazırlayalım")
    m_id = st.text_input("Metin ID:", "Metin_1")
    up = st.file_uploader("Metni PDF olarak yükle", type="pdf")
    txt = st.text_area("Veya metni buraya kopyala")

    if st.button("Metni Hazırla ✨") and (up or txt):
        raw = (txt or "").strip()
        if up:
            reader = PdfReader(up)
            parts = []
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    parts.append(t)
            raw = "\n".join(parts).strip()

        if not raw:
            st.error("Metin boş görünüyor. PDF metin çıkarılamamış olabilir.")
            st.stop()

        log_chat("TEXT_PREP_START", json.dumps({"metin_id": m_id}, ensure_ascii=False))

        with st.spinner("Metni düzenliyorum..."):
            prompt = (
                "ÖÖG uzmanı olarak metni ortaokul öğrencisi için sadeleştir. "
                "6 soru içeren saf JSON üret. "
                "Şema: {'sade_metin':'...','sorular':[{'kok':'...','A':'...','B':'...','C':'...','dogru':'A','ipucu':'...'}]}"
            )
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": raw}
                ],
                response_format={"type": "json_object"}
            )

            st.session_state.activity = json.loads(resp.choices[0].message.content)
            st.session_state.metin_id = m_id
            st.session_state.phase = "read"
            st.session_state.q_idx = 0
            st.session_state.correct_map = {}
            st.session_state.hints = 0
            st.session_state.start_t = time.time()
            st.session_state.saved_perf = False

            log_chat("TEXT_PREP_DONE", json.dumps({"metin_id": m_id}, ensure_ascii=False))
            st.rerun()

# =========================================================
# 3) OKUMA + SOHBET
# =========================================================
elif st.session_state.phase == "read":
    act = st.session_state.activity
    metin = act.get("sade_metin") or act.get("metin") or "Metin içeriği alınamadı."

    st.markdown(f"<div class='highlight-box'>{metin}</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Sesli Dinle"):
            log_chat("AUDIO_PLAY", f"metin_id={st.session_state.get('metin_id','')}")
            st.audio(get_audio(metin), format="audio/mp3")

    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor")

    user_q = st.chat_input("Metinde anlamadığın bir yer var mı?")
    if user_q:
        log_chat("CHAT_Q", user_q)

        ai_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Sen ÖÖG öğretmenisin. Şu metne göre yardım et: {metin}"},
                {"role": "user", "content": user_q}
            ]
        )
        answer = ai_resp.choices[0].message.content
        log_chat("CHAT_A", answer)

        st.session_state.chat_history.append({"q": user_q, "a": answer})

    for chat in st.session_state.chat_history:
        st.chat_message("user").write(chat["q"])
        st.chat_message("assistant").write(chat["a"])

    if st.button("Sorulara Geç ➜"):
        log_chat("GO_TO_QUESTIONS", "clicked")
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 4) SORULAR + İPUCU
# =========================================================
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get("sorular", [])
    i = st.session_state.q_idx

    if not sorular:
        st.error("Sorular bulunamadı. Üretilen JSON içinde 'sorular' alanı yok.")
        st.stop()

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")
        st.markdown(f"<div style='font-size:22px; margin-bottom:14px;'>{q.get('kok','')}</div>", unsafe_allow_html=True)

        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt,'')}", key=f"q_{i}_{opt}"):
                is_correct = (opt == q.get("dogru"))
                st.session_state.correct_map[i] = 1 if is_correct else 0

                log_chat("ANSWER", json.dumps({
                    "q_idx": i+1,
                    "selected": opt,
                    "correct": q.get("dogru"),
                    "is_correct": is_correct
                }, ensure_ascii=False))

                if is_correct:
                    st.success("🌟 Doğru!")
                    time.sleep(0.35)
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.error("Tekrar dene!")

        if st.button("💡 İpucu Al", key=f"hint_{i}"):
            st.session_state.hints += 1
            log_chat("HINT", json.dumps({"q_idx": i+1}, ensure_ascii=False))
            st.warning(q.get("ipucu", "Metne tekrar bakabilirsin!"))

        st.markdown("<div class='small-note'>Not: İstersen çıkış yapıp sonra tekrar başlayabilirsin.</div>", unsafe_allow_html=True)

    else:
        # ✅ PERFORMANS KAYDI
        if not st.session_state.saved_perf:
            dogru = sum(st.session_state.correct_map.values())
            sure = round((time.time() - st.session_state.start_t) / 60, 2)

            wrongs = [str(idx + 1) for idx, v in st.session_state.correct_map.items() if v == 0]
            hatali = "Yanlış: " + ",".join(wrongs) if wrongs else "Hepsi doğru"

            row = [
                st.session_state.session_id,
                st.session_state.user,
                st.session_state.login_time,
                sure,
                st.session_state.sinif,
                f"%{round(dogru/6*100, 1)}",
                6,
                dogru,
                hatali,
                st.session_state.metin_id,
                st.session_state.hints,
                "Evet", "Evet", 0, 0
            ]

            ok = save_to_sheets(row, sheet_name="Performans")
            if ok:
                log_chat("PERF_SAVED", json.dumps({"dogru": dogru, "sure": sure}, ensure_ascii=False))
                st.session_state.saved_perf = True
                st.session_state.phase = "done"
                st.rerun()
        else:
            st.session_state.phase = "done"
            st.rerun()

# =========================================================
# 5) BİTTİ
# =========================================================
elif st.session_state.phase == "done":
    st.balloons()
    st.success("✅ Bugünkü çalışman kaydedildi!")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yeni Metin"):
            log_chat("NEW_TEXT", "clicked")
            st.session_state.phase = "setup"
            st.session_state.chat_history = []
            st.session_state.saved_perf = False
            st.rerun()
    with c2:
        if st.button("Çıkış"):
            log_chat("LOGOUT", "done_screen")
            st.session_state.clear()
            st.rerun()
