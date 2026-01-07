import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError
import json, uuid, time, re, random, traceback
from gtts import gTTS
from io import BytesIO

# =========================================================
# OKUMA DOSTUM — STRATEJİ TEMELLİ OKUMA (ÖÖG)
# PRE / DURING / POST + STORY MAP + SHEETS LOG + RATE LIMIT KORUMA
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
  .card {
    background:#fff; padding:16px; border-radius:18px;
    border:1px solid #eee; margin-bottom:10px;
  }
</style>
""", unsafe_allow_html=True)

# =========================================================
# OPENAI CLIENT + RATE LIMIT KORUMA
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def openai_json_request(system_prompt, user_text, model="gpt-4o-mini", max_retries=6):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format={"type": "json_object"},
            )
        except (RateLimitError, APIError, APITimeoutError):
            wait = min(2 ** attempt, 20) + random.uniform(0, 1.0)
            st.warning(f"⚠️ Yoğunluk var, tekrar deneniyor... ({attempt+1}/{max_retries})")
            time.sleep(wait)

    st.error("❌ OpenAI yoğunluğu çok fazla. 30 sn sonra tekrar deneyin.")
    st.stop()

# =========================================================
# GOOGLE SHEETS (STABİL)
# =========================================================
@st.cache_resource
def get_gs_client():
    info = dict(st.secrets["GSHEETS"])
    pk = info.get("private_key", "")
    if isinstance(pk, str) and "\\n" in pk:
        info["private_key"] = pk.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    return get_gs_client().open_by_url(st.secrets["GSHEET_URL"])

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

def log_chat(event, payload):
    """Sohbet sekmesine süreç logu yazar."""
    try:
        ts = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")
        row = [
            st.session_state.get("session_id", ""),
            st.session_state.get("user", ""),
            ts,
            event,
            payload[:45000] if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)[:45000],
        ]
        save_to_sheets(row, sheet_name="Sohbet")
    except Exception:
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
# Metni paragraflara böl
# =========================================================
def split_paragraphs(text: str):
    text = text.replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        if len(parts) > 8:
            chunks, buf = [], ""
            for s in parts:
                if len(buf) < 260:
                    buf = (buf + " " + s).strip()
                else:
                    chunks.append(buf); buf = s
            if buf: chunks.append(buf)
            parts = chunks
    return parts

# =========================================================
# SESSION STATE
# =========================================================
if "phase" not in st.session_state: st.session_state.phase = "auth"
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "saved_perf" not in st.session_state: st.session_state.saved_perf = False
if "login_logged" not in st.session_state: st.session_state.login_logged = False
if "busy" not in st.session_state: st.session_state.busy = False

# strateji state
if "prediction" not in st.session_state: st.session_state.prediction = ""
if "attention_ok" not in st.session_state: st.session_state.attention_ok = False
if "reading_speed" not in st.session_state: st.session_state.reading_speed = "Orta"
if "repeat_count" not in st.session_state: st.session_state.repeat_count = 0
if "important_notes" not in st.session_state: st.session_state.important_notes = []
if "prior_knowledge" not in st.session_state: st.session_state.prior_knowledge = ""
if "summary" not in st.session_state: st.session_state.summary = ""

# story map state
if "story_map" not in st.session_state:
    st.session_state.story_map = {
        "kahraman": "",
        "mekan": "",
        "zaman": "",
        "problem": "",
        "olaylar": "",
        "cozum": ""
    }
if "story_map_saved" not in st.session_state:
    st.session_state.story_map_saved = False

# Global çıkış
if st.session_state.phase != "auth":
    col_a, col_b = st.columns([9, 1])
    with col_b:
        if st.button("Çıkış 🚪"):
            log_chat("LOGOUT", "user_clicked")
            st.session_state.clear()
            st.rerun()

# =========================================================
# 1) GİRİŞ
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum'a Hoş Geldin!")
    u = st.text_input("Öğrenci Kodun (örn: S5-014):")
    s = st.selectbox("Sınıfın:", ["5", "6", "7", "8"])

    if st.button("Hadi Başlayalım! 🚀") and u:
        st.session_state.user = u
        st.session_state.sinif = s
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")

        # reset
        st.session_state.chat_history = []
        st.session_state.saved_perf = False
        st.session_state.busy = False

        st.session_state.prediction = ""
        st.session_state.attention_ok = False
        st.session_state.reading_speed = "Orta"
        st.session_state.repeat_count = 0
        st.session_state.important_notes = []
        st.session_state.prior_knowledge = ""
        st.session_state.summary = ""

        st.session_state.story_map = {
            "kahraman": "",
            "mekan": "",
            "zaman": "",
            "problem": "",
            "olaylar": "",
            "cozum": ""
        }
        st.session_state.story_map_saved = False

        log_chat("LOGIN", json.dumps({"sinif": s, "login_time": st.session_state.login_time}, ensure_ascii=False))
        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) METİN HAZIRLAMA
# =========================================================
elif st.session_state.phase == "setup":
    st.subheader("📄 Okuyacağımız Metni Hazırlayalım")
    m_id = st.text_input("Metin ID:", "Metin_1")
    up = st.file_uploader("Metni PDF olarak yükle", type="pdf")
    txt = st.text_area("Veya metni buraya kopyala")

    if st.button("Metni Hazırla ✨") and (up or txt):
        if st.session_state.busy:
            st.warning("İşleniyor... Lütfen bekle.")
            st.stop()
        st.session_state.busy = True

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
            st.session_state.busy = False
            st.error("Metin boş görünüyor. PDF metin çıkarılamamış olabilir.")
            st.stop()

        # istek küçült: rate limit koruma
        raw = raw[:12000]

        log_chat("TEXT_PREP_START", json.dumps({"metin_id": m_id}, ensure_ascii=False))

        # sınıf düzeyi hedefli sadeleştirme
        grade = st.session_state.sinif
        grade_hint = {
            "5": "Çok sade, kısa cümleler, somut kelimeler, 120-180 kelime hedefle.",
            "6": "Sade, kısa-orta cümleler, 150-220 kelime hedefle.",
            "7": "Orta düzey, 180-260 kelime hedefle.",
            "8": "Biraz daha akademik ama anlaşılır, 200-320 kelime hedefle.",
        }.get(str(grade), "Sade ve anlaşılır yaz.")

        prompt = (
            "ÖÖG uzmanı olarak metni ortaokul öğrencisi için sadeleştir. "
            f"Hedef sınıf: {grade}. {grade_hint} "
            "Ayrıca 6 soru içeren saf JSON üret. "
            "Şema: {'sade_metin':'...','sorular':[{'kok':'...','A':'...','B':'...','C':'...','dogru':'A','tur':'literal/inferential/main_idea','ipucu':'...'}]}"
        )

        with st.spinner("Metni düzenliyorum..."):
            resp = openai_json_request(prompt, raw, model="gpt-4o-mini")
            st.session_state.activity = json.loads(resp.choices[0].message.content)

        st.session_state.metin_id = m_id
        metin = st.session_state.activity.get("sade_metin") or ""
        st.session_state.paragraphs = split_paragraphs(metin)
        st.session_state.p_idx = 0

        # soru aşaması için reset
        st.session_state.q_idx = 0
        st.session_state.correct_map = {}
        st.session_state.hints = 0
        st.session_state.start_t = time.time()
        st.session_state.saved_perf = False

        # strateji reset
        st.session_state.prediction = ""
        st.session_state.attention_ok = False
        st.session_state.reading_speed = "Orta"
        st.session_state.repeat_count = 0
        st.session_state.important_notes = []
        st.session_state.prior_knowledge = ""
        st.session_state.summary = ""
        st.session_state.story_map = {
            "kahraman": "",
            "mekan": "",
            "zaman": "",
            "problem": "",
            "olaylar": "",
            "cozum": ""
        }
        st.session_state.story_map_saved = False

        log_chat("TEXT_PREP_DONE", json.dumps({"metin_id": m_id, "paragraphs": len(st.session_state.paragraphs)}, ensure_ascii=False))
        st.session_state.busy = False

        st.session_state.phase = "pre"
        st.rerun()

# =========================================================
# 3) PRE-READING
# =========================================================
elif st.session_state.phase == "pre":
    st.subheader("🟦 Okuma Öncesi (PRE-READING)")

    st.markdown("<div class='card'><b>1) Merak Uyandırma</b><br/>Bu metinde ilginç bir durum var. Sence ne olabilir?</div>", unsafe_allow_html=True)
    curiosity = st.text_input("Tahminin (1 cümle):", value=st.session_state.prediction)

    st.markdown("<div class='card'><b>2) Dikkat Toplama</b><br/>Şimdi metni dikkatle okuyacağız. Hazır mısın?</div>", unsafe_allow_html=True)
    attention = st.checkbox("✅ Hazırım (dikkatimi veriyorum)", value=st.session_state.attention_ok)

    st.markdown("<div class='card'><b>3) Okuma Hızı Seç</b><br/>Bugün nasıl okumak istersin?</div>", unsafe_allow_html=True)
    speed = st.radio("Okuma hızı:", ["Yavaş", "Orta", "Hızlı"], index=["Yavaş","Orta","Hızlı"].index(st.session_state.reading_speed))

    if st.button("Okumaya Başla ➜"):
        st.session_state.prediction = curiosity.strip()
        st.session_state.attention_ok = attention
        st.session_state.reading_speed = speed

        log_chat("PRE_PREDICTION", st.session_state.prediction)
        log_chat("PRE_ATTENTION", json.dumps({"attention_ok": bool(attention)}, ensure_ascii=False))
        log_chat("PRE_SPEED", speed)

        st.session_state.phase = "during"
        st.rerun()

# =========================================================
# 4) DURING-READING
# =========================================================
elif st.session_state.phase == "during":
    st.subheader("🟩 Okuma Sırası (DURING-READING)")

    act = st.session_state.activity
    metin = act.get("sade_metin") or "Metin yok."
    paras = st.session_state.get("paragraphs", split_paragraphs(metin))
    p_idx = st.session_state.get("p_idx", 0)

    # Sesli dinleme
    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Sesli Dinle"):
            st.session_state.repeat_count += 1
            log_chat("DURING_AUDIO_PLAY", json.dumps({"repeat_count": st.session_state.repeat_count}, ensure_ascii=False))
            st.audio(get_audio(metin), format="audio/mp3")

    st.markdown(f"<div class='small-note'>Seçtiğin hız: <b>{st.session_state.reading_speed}</b> | Tekrar okuma/dinleme: <b>{st.session_state.repeat_count}</b></div>", unsafe_allow_html=True)
    st.divider()

    if p_idx < len(paras):
        st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)

        note = st.text_input("Bu paragrafta en önemli şey neydi? (1 cümle)", key=f"imp_{p_idx}")
        coln1, coln2, coln3 = st.columns(3)
        with coln1:
            if st.button("📌 Kaydet (Önemli)", key=f"save_imp_{p_idx}"):
                if note.strip():
                    st.session_state.important_notes.append({"p": p_idx+1, "note": note.strip()})
                    log_chat("DURING_IMPORTANT_NOTE", json.dumps({"p": p_idx+1, "note": note.strip()}, ensure_ascii=False))
                    st.success("Kaydedildi!")
                else:
                    st.warning("Bir cümle yaz.")
        with coln2:
            if st.button("🔁 Bu paragrafı tekrar oku", key=f"repeat_p_{p_idx}"):
                st.session_state.repeat_count += 1
                log_chat("DURING_REPEAT_P", json.dumps({"p": p_idx+1, "repeat_count": st.session_state.repeat_count}, ensure_ascii=False))
                st.info("Tekrar okudun. İstersen not ekleyebilirsin.")
        with coln3:
            if st.button("➡️ Sonraki paragraf", key=f"next_p_{p_idx}"):
                st.session_state.p_idx = p_idx + 1
                st.rerun()
    else:
        st.markdown("<div class='card'><b>Ön Bilgi</b><br/>Bu metin sana daha önce yaşadığın/duyduğun bir şeyi hatırlattı mı?</div>", unsafe_allow_html=True)
        pk = st.text_area("Varsa kısaca yaz:", value=st.session_state.prior_knowledge, height=100)

        if st.button("Okuma Sonrasına Geç ➜"):
            st.session_state.prior_knowledge = pk.strip()
            log_chat("DURING_PRIOR_KNOWLEDGE", st.session_state.prior_knowledge)
            st.session_state.phase = "post"
            st.rerun()

# =========================================================
# 5) POST-READING (ÖZET + ÖYKÜ HARİTASI + SOHBET + SORULARA GEÇ)
# =========================================================
elif st.session_state.phase == "post":
    st.subheader("🟧 Okuma Sonrası (POST-READING)")

    act = st.session_state.activity
    metin = act.get("sade_metin") or "Metin yok."

    st.markdown("<div class='card'><b>Özetleme</b><br/>Metni 2–3 cümleyle anlat.</div>", unsafe_allow_html=True)
    summ = st.text_area("Özetin:", value=st.session_state.summary, height=120)

    if st.button("Özeti Kaydet ✅"):
        st.session_state.summary = summ.strip()
        log_chat("POST_SUMMARY", st.session_state.summary)
        st.success("✅ Özet kaydedildi!")

    # ---- STORY MAP ----
    st.divider()
    st.subheader("🗺️ Öykü Haritası (Story Map)")
    st.markdown("""
    <div class='card'>
    <b>Nasıl dolduracaksın?</b><br/>
    Metindeki öykünün parçalarını tek tek yaz. Kısa yazman yeterli (1–2 cümle).
    </div>
    """, unsafe_allow_html=True)

    sm = st.session_state.story_map

    col1, col2 = st.columns(2)
    with col1:
        sm["kahraman"] = st.text_input("👤 Kahraman(lar)", value=sm["kahraman"])
        sm["mekan"] = st.text_input("🏠 Mekân", value=sm["mekan"])
        sm["zaman"] = st.text_input("🕒 Zaman", value=sm["zaman"])
    with col2:
        sm["problem"] = st.text_input("⚠️ Problem (Sorun)", value=sm["problem"])
        sm["olaylar"] = st.text_area("🔁 Olaylar (Kısaca sırayla)", value=sm["olaylar"], height=90)
        sm["cozum"] = st.text_input("✅ Çözüm / Sonuç", value=sm["cozum"])

    st.session_state.story_map = sm

    col_a, col_b = st.columns([2, 1])
    with col_a:
        if st.button("🗂️ Öykü Haritasını Kaydet"):
            filled = sum(1 for _, v in sm.items() if str(v).strip())
            if filled < 3:
                st.warning("En az 3 alanı doldur (ör. kahraman, mekân, problem).")
            else:
                payload = {
                    "metin_id": st.session_state.get("metin_id", ""),
                    "sinif": st.session_state.get("sinif", ""),
                    "story_map": sm
                }
                log_chat("STORY_MAP", json.dumps(payload, ensure_ascii=False))
                st.session_state.story_map_saved = True
                st.success("✅ Öykü haritası kaydedildi!")
    with col_b:
        st.markdown("<div class='small-note'>Kayıt: ✅</div>" if st.session_state.story_map_saved else "<div class='small-note'>Kayıt: ⏳</div>", unsafe_allow_html=True)

    if not st.session_state.story_map_saved:
        st.info("İstersen önce 🗺️ Öykü Haritasını doldurabilirsin (önerilir).")

    # ---- SOHBET ----
    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor (İsteğe bağlı)")
    user_q = st.chat_input("Metinle ilgili soru sorabilirsin…")
    if user_q:
        log_chat("CHAT_Q", user_q)
        ai_resp = client.chat.completions.create(
            model="gpt-4o-mini",
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
# 6) SORULAR + İPUCU
# =========================================================
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act.get("sorular", [])
    i = st.session_state.q_idx

    if not sorular:
        st.error("Sorular bulunamadı. JSON içinde 'sorular' alanı yok.")
        st.stop()

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")

        tur = q.get("tur", "")
        if tur:
            st.markdown(f"<div class='small-note'>Soru türü: <b>{tur}</b></div>", unsafe_allow_html=True)

        st.markdown(f"<div style='font-size:22px; margin-bottom:14px;'>{q.get('kok','')}</div>", unsafe_allow_html=True)

        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt,'')}", key=f"q_{i}_{opt}"):
                is_correct = (opt == q.get("dogru"))
                st.session_state.correct_map[i] = 1 if is_correct else 0

                log_chat("ANSWER", json.dumps({
                    "q_idx": i+1,
                    "tur": tur,
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

    else:
        if not st.session_state.saved_perf:
            dogru = sum(st.session_state.correct_map.values())
            sure = round((time.time() - st.session_state.start_t) / 60, 2)
            wrongs = [str(idx + 1) for idx, v in st.session_state.correct_map.items() if v == 0]
            hatali = "Yanlış: " + ",".join(wrongs) if wrongs else "Hepsi doğru"

            strat = {
                "prediction": st.session_state.prediction,
                "attention_ok": st.session_state.attention_ok,
                "reading_speed": st.session_state.reading_speed,
                "repeat_count": st.session_state.repeat_count,
                "important_notes_count": len(st.session_state.important_notes),
                "prior_knowledge": st.session_state.prior_knowledge,
                "summary_len": len(st.session_state.summary or ""),
                "story_map_saved": st.session_state.story_map_saved,
                "story_map_filled": sum(1 for _, v in st.session_state.story_map.items() if str(v).strip())
            }
            log_chat("STRATEGY_SUMMARY", json.dumps(strat, ensure_ascii=False))

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
# 7) BİTTİ
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
            st.session_state.busy = False

            st.session_state.story_map = {
                "kahraman": "",
                "mekan": "",
                "zaman": "",
                "problem": "",
                "olaylar": "",
                "cozum": ""
            }
            st.session_state.story_map_saved = False
            st.rerun()
    with c2:
        if st.button("Çıkış"):
            log_chat("LOGOUT", "done_screen")
            st.session_state.clear()
            st.rerun()
