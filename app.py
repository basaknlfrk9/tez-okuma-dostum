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

# =========================================================
# OKUMA DOSTUM — BANKA SÜRÜMÜ (METİN + SORU SHEETS'TEN)
# MetinBankasi: metin_id | sinif | metin | baslik | pre_ipucu
# SoruBankasi : metin_id | sinif | soru_no | kok | A | B | C | dogru
# Performans   : (kayıt)
# OykuHaritasi : (story map + AI puan)
# OkumaSüreci  : session_id | ogrenci_kodu | tarih_saat | sinif | metin_id | paragraf_no | kayit_turu | icerik
#
# NOT: Sohbet/log sistemi KAPALI (log_chat no-op)
# =========================================================
st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap');
  html, body, [class*="css"] { font-family: 'Lexend', sans-serif; font-size: 20px; }
  .stButton button {
    width: 100%; border-radius: 18px; height: 3.0em;
    font-weight: 600; font-size: 20px !important;
    border: 2px solid #eee; background-color: #3498db; color: white;
  }
  .highlight-box {
    background-color: #ffffff; padding: 26px; border-radius: 22px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.08);
    border-left: 12px solid #f1c40f; font-size: 22px !important;
    line-height: 1.9 !important; margin-bottom: 18px;
  }
  .small-note { color:#666; font-size:16px; }
  .card { background:#fff; padding:16px; border-radius:18px; border:1px solid #eee; margin-bottom:10px; }
  .report-card { background:#fff; padding:18px; border-radius:18px; border:1px solid #eee; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def _norm(x) -> str:
    return str(x or "").strip()

def now_tr() -> str:
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

def split_paragraphs(text: str):
    text = (text or "").replace("\r", "\n").strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        if len(parts) > 8:
            chunks, buf = [], ""
            for s in parts:
                if len(buf) < 260:
                    buf = (buf + " " + s).strip()
                else:
                    chunks.append(buf)
                    buf = s
            if buf:
                chunks.append(buf)
            parts = chunks
    return parts

def get_audio(text: str):
    clean = re.sub(r"[*#_]", "", (text or ""))[:1000]
    try:
        tts = gTTS(text=clean, lang="tr")
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception:
        st.error("❌ Ses oluşturulamadı. Lütfen tekrar deneyin.")
        return None

# =========================================================
# OPENAI
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
    st.error("❌ OpenAI yoğunluğu çok fazla. Biraz sonra tekrar deneyin.")
    st.stop()

# =========================================================
# GOOGLE SHEETS
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

def append_row_safe(sheet_name: str, row):
    try:
        ws = get_ws(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        st.error(f"❌ Sheets yazma hatası ({sheet_name})")
        st.code(traceback.format_exc())
        return False

# =========================================================
# SOHBET LOG KAPALI
# =========================================================
def log_chat(event: str, payload):
    return

# =========================================================
# OKUMA SÜRECİ KAYDI (YENİ)
# =========================================================
def save_reading_process(kayit_turu: str, icerik: str, paragraf_no=None):
    """
    OkumaSüreci sekmesine tek satır kayıt atar.
    OkumaSüreci başlık önerisi:
    session_id | ogrenci_kodu | tarih_saat | sinif | metin_id | paragraf_no | kayit_turu | icerik
    """
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        st.session_state.get("sinif", ""),
        st.session_state.get("metin_id", ""),
        paragraf_no if paragraf_no is not None else "",
        kayit_turu,
        (icerik or "")[:45000],
    ]
    append_row_safe("OkumaSüreci", row)

# =========================================================
# BANKA OKUMA
# =========================================================
def list_metin_ids_for_sinif(sinif: str):
    ws = get_ws("MetinBankasi")
    rows = ws.get_all_records()
    ids = []
    for r in rows:
        if _norm(r.get("sinif")) == _norm(sinif) and _norm(r.get("metin_id")):
            ids.append(_norm(r.get("metin_id")))
    return sorted(list(set(ids)))

def load_activity_from_bank(metin_id: str, sinif: str):
    ws_m = get_ws("MetinBankasi")
    mrows = ws_m.get_all_records()
    match_m = [
        r for r in mrows
        if _norm(r.get("metin_id")) == _norm(metin_id) and _norm(r.get("sinif")) == _norm(sinif)
    ]
    if not match_m:
        return None, "MetinBankasi'nda bu metin_id + sınıf bulunamadı."

    metin = _norm(match_m[0].get("metin"))
    baslik = _norm(match_m[0].get("baslik"))
    pre_ipucu = _norm(match_m[0].get("pre_ipucu"))
    if not metin:
        return None, "MetinBankasi'nda metin alanı boş."

    ws_q = get_ws("SoruBankasi")
    qrows = ws_q.get_all_records()
    match_q = [
        r for r in qrows
        if _norm(r.get("metin_id")) == _norm(metin_id) and _norm(r.get("sinif")) == _norm(sinif)
    ]
    if not match_q:
        return None, "SoruBankasi'nda bu metin_id + sınıf için soru bulunamadı."

    def qno(r):
        try:
            return int(str(r.get("soru_no", "")).strip())
        except Exception:
            return 0

    match_q = sorted(match_q, key=qno)

    sorular = []
    for r in match_q:
        q = {
            "kok": _norm(r.get("kok")),
            "A": _norm(r.get("A")),
            "B": _norm(r.get("B")),
            "C": _norm(r.get("C")),
            "dogru": _norm(r.get("dogru")).upper() or "A",
        }
        if q["dogru"] not in ["A", "B", "C"]:
            q["dogru"] = "A"
        sorular.append(q)

    if len(sorular) != 6:
        return None, f"Soru sayısı 6 olmalı. Bulunan: {len(sorular)}"

    return {"sade_metin": metin, "baslik": baslik, "pre_ipucu": pre_ipucu, "sorular": sorular}, ""

# =========================================================
# STORY MAP AI
# =========================================================
def ai_score_story_map(metin: str, sm: dict, grade: str):
    metin_short = (metin or "")[:2500]
    sm_safe = {k: (v or "")[:600] for k, v in (sm or {}).items()}

    rubrik = """
Rubrik (0-2):
0 = boş / alakasız / metinle uyuşmuyor
1 = kısmen doğru ama eksik / belirsiz
2 = doğru ve metinle uyumlu (kısa da olsa doğru bilgi)
"""
    schema = """
Sadece JSON üret:
{
  "scores": {"kahraman":0|1|2,"mekan":0|1|2,"zaman":0|1|2,"problem":0|1|2,"olaylar":0|1|2,"cozum":0|1|2},
  "total": 0-12,
  "reason": "1-2 cümle Türkçe kısa gerekçe"
}
total = scores toplamı olmalı.
"""
    sys = f"""
Sen özel eğitim/ÖÖG alanında deneyimli bir öğretmensin.
{grade}. sınıf düzeyine göre değerlendir.
{rubrik}
{schema}
"""
    user = json.dumps({"metin": metin_short, "story_map": sm_safe}, ensure_ascii=False)
    resp = openai_json_request(sys, user, model="gpt-4o-mini")
    data = json.loads(resp.choices[0].message.content)

    scores = data.get("scores", {})
    def clamp02(x):
        try:
            x = int(x)
        except Exception:
            x = 0
        return 0 if x < 0 else 2 if x > 2 else x

    out = {
        "kahraman": clamp02(scores.get("kahraman", 0)),
        "mekan": clamp02(scores.get("mekan", 0)),
        "zaman": clamp02(scores.get("zaman", 0)),
        "problem": clamp02(scores.get("problem", 0)),
        "olaylar": clamp02(scores.get("olaylar", 0)),
        "cozum": clamp02(scores.get("cozum", 0)),
    }
    total = sum(out.values())
    reason = (data.get("reason") or "").strip()[:200]
    return out, total, reason

def save_story_map_row(sm: dict, scores: dict, total: int, reason: str):
    row = [
        st.session_state.get("session_id", ""),
        st.session_state.get("user", ""),
        now_tr(),
        st.session_state.get("sinif", ""),
        st.session_state.get("metin_id", ""),
        sm.get("kahraman", ""),
        sm.get("mekan", ""),
        sm.get("zaman", ""),
        sm.get("problem", ""),
        sm.get("olaylar", ""),
        sm.get("cozum", ""),
        sum(1 for _, v in sm.items() if str(v).strip()),
        scores.get("kahraman", 0),
        scores.get("mekan", 0),
        scores.get("zaman", 0),
        scores.get("problem", 0),
        scores.get("olaylar", 0),
        scores.get("cozum", 0),
        total,
        reason,
    ]
    return append_row_safe("OykuHaritasi", row)

# =========================================================
# SESSION STATE INIT
# =========================================================
def reset_activity_states():
    st.session_state.chat_history = []
    st.session_state.saved_perf = False
    st.session_state.busy = False

    # PRE
    st.session_state.prediction = ""
    st.session_state.attention_ok = False
    st.session_state.reading_speed = "Orta"

    # DURING
    st.session_state.repeat_count = 0        # toplam tekrar (dinleme + tekrar okuma)
    st.session_state.tts_count = 0           # sadece "dinle" sayısı
    st.session_state.reread_count = 0        # sadece "tekrar oku" sayısı
    st.session_state.important_notes = []    # [{"p":1,"note":"..."}]
    st.session_state.prior_knowledge = ""

    # POST
    st.session_state.summary = ""

    # STORY MAP
    st.session_state.story_map = {"kahraman":"", "mekan":"", "zaman":"", "problem":"", "olaylar":"", "cozum":""}
    st.session_state.story_map_ai_scored = False
    st.session_state.story_map_last_total = None
    st.session_state.story_map_last_reason = ""
    st.session_state.story_map_filled = 0

    # QUESTIONS
    st.session_state.skipped = []
    st.session_state.hints_used_by_q = {}
    st.session_state.correct_no_hint = 0
    st.session_state.correct_with_hint = 0
    st.session_state.question_attempts = {}
    st.session_state.show_text_in_questions = False

if "phase" not in st.session_state:
    st.session_state.phase = "auth"
if "busy" not in st.session_state:
    st.session_state.busy = False

# Global çıkış
if st.session_state.phase != "auth":
    col_a, col_b = st.columns([9, 1])
    with col_b:
        if st.button("Çıkış 🚪"):
            st.session_state.clear()
            st.rerun()

# =========================================================
# 1) AUTH
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
        reset_activity_states()
        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) SETUP (BANKADAN METİN SEÇ)
# =========================================================
elif st.session_state.phase == "setup":
    st.subheader("📄 Metin Seç (Sistemden)")

    sinif = st.session_state.sinif
    try:
        metin_ids = list_metin_ids_for_sinif(sinif)
    except Exception:
        metin_ids = []
        st.error("❌ MetinBankasi okunamadı. Sekme adlarını ve erişimi kontrol et.")
        st.code(traceback.format_exc())

    selected_id = st.selectbox("Metin ID seç:", metin_ids) if metin_ids else st.text_input("Metin ID:", "Metin_001")
    st.caption("Metin ve sorular Google Sheets bankasından çekilir.")

    if st.button("Metni Hazırla ✨", disabled=st.session_state.busy):
        st.session_state.busy = True

        activity, err = load_activity_from_bank(selected_id, sinif)
        if activity is None:
            st.session_state.busy = False
            st.error(f"❌ Yüklenemedi: {err}")
            st.stop()

        st.session_state.activity = activity
        st.session_state.metin_id = selected_id
        st.session_state.paragraphs = split_paragraphs(activity.get("sade_metin", ""))
        st.session_state.p_idx = 0

        st.session_state.q_idx = 0
        st.session_state.correct_map = {}
        st.session_state.hints = 0
        st.session_state.start_t = time.time()
        st.session_state.saved_perf = False

        # oturum başı süreç özeti kaydı (opsiyonel ama faydalı)
        save_reading_process("SESSION_START", f"Metin yüklendi: {selected_id}", paragraf_no=None)

        st.session_state.show_text_in_questions = False
        st.session_state.busy = False

        st.session_state.phase = "pre"
        st.rerun()

# =========================================================
# 3) PRE
# =========================================================
elif st.session_state.phase == "pre":
    st.subheader("🟦 Okuma Öncesi (PRE-READING)")

    baslik = st.session_state.activity.get("baslik", "")
    pre_ipucu = st.session_state.activity.get("pre_ipucu", "")

    if baslik:
        st.markdown(f"<div class='card'><b>Metnin Başlığı</b><br/>{baslik}</div>", unsafe_allow_html=True)
    if pre_ipucu:
        st.markdown(f"<div class='card'><b>Küçük İpucu</b><br/>{pre_ipucu}</div>", unsafe_allow_html=True)

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

        # planlama verilerini OkumaSüreci'ne yaz
        if st.session_state.prediction:
            save_reading_process("PRE_PREDICTION", st.session_state.prediction, paragraf_no=None)
        save_reading_process("PRE_ATTENTION", "Evet" if attention else "Hayır", paragraf_no=None)
        save_reading_process("PRE_SPEED", speed, paragraf_no=None)

        st.session_state.phase = "during"
        st.rerun()

# =========================================================
# 4) DURING
# =========================================================
elif st.session_state.phase == "during":
    st.subheader("🟩 Okuma Sırası (DURING-READING)")

    metin = st.session_state.activity.get("sade_metin", "Metin yok.")
    paras = st.session_state.get("paragraphs", split_paragraphs(metin))
    p_idx = st.session_state.get("p_idx", 0)

    c1, c2 = st.columns([2, 5])
    with c1:
        if st.button("🔊 Bu paragrafı dinle"):
            st.session_state.repeat_count += 1
            st.session_state.tts_count += 1
            current_para = paras[p_idx] if (0 <= p_idx < len(paras)) else metin

            # TTS kullanımını kaydet
            save_reading_process("TTS_PLAY", "Paragraf dinlendi", paragraf_no=p_idx+1)

            fp = get_audio(current_para)
            if fp:
                st.audio(fp, format="audio/mp3")

    with c2:
        st.markdown(
            f"<div class='small-note'>Seçtiğin hız: <b>{st.session_state.reading_speed}</b> | "
            f"Tekrar okuma/dinleme: <b>{st.session_state.repeat_count}</b> | "
            f"Paragraf: <b>{min(p_idx+1, len(paras))}/{len(paras)}</b></div>",
            unsafe_allow_html=True
        )

    st.divider()

    if p_idx < len(paras):
        st.markdown(f"<div class='highlight-box'>{paras[p_idx]}</div>", unsafe_allow_html=True)

        note = st.text_input("Bu paragrafta en önemli şey neydi? (1 cümle)", key=f"imp_{p_idx}")
        coln1, coln2, coln3 = st.columns(3)

        with coln1:
            if st.button("📌 Kaydet (Önemli)", key=f"save_imp_{p_idx}"):
                if note.strip():
                    st.session_state.important_notes.append({"p": p_idx+1, "note": note.strip()})
                    # önemli notu kaydet (izleme)
                    save_reading_process("IMPORTANT_NOTE", note.strip(), paragraf_no=p_idx+1)
                    st.success("Kaydedildi!")
                else:
                    st.warning("Bir cümle yaz.")

        with coln2:
            if st.button("🔁 Bu paragrafı tekrar oku", key=f"repeat_p_{p_idx}"):
                st.session_state.repeat_count += 1
                st.session_state.reread_count += 1
                # tekrar okumayı kaydet (izleme)
                save_reading_process("REPEAT_READ", "Paragraf tekrar okundu", paragraf_no=p_idx+1)
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
            if pk.strip():
                # ön bilgi aktivasyonu (planlama/izleme)
                save_reading_process("PRIOR_KNOWLEDGE", pk.strip(), paragraf_no=None)
            else:
                save_reading_process("PRIOR_KNOWLEDGE", "(boş)", paragraf_no=None)

            st.session_state.phase = "post"
            st.rerun()

# =========================================================
# 5) POST
# =========================================================
elif st.session_state.phase == "post":
    st.subheader("🟧 Okuma Sonrası (POST-READING)")
    metin = st.session_state.activity.get("sade_metin", "Metin yok.")

    st.markdown("<div class='card'><b>Özetleme</b><br/>Metni 2–3 cümleyle anlat.</div>", unsafe_allow_html=True)
    summ = st.text_area("Özetin:", value=st.session_state.summary, height=120)

    if st.button("Özeti Kaydet ✅"):
        st.session_state.summary = summ.strip()
        if st.session_state.summary:
            save_reading_process("POST_SUMMARY", st.session_state.summary, paragraf_no=None)
        st.success("✅ Özet kaydedildi!")

    st.divider()
    st.subheader("🗺️ Öykü Haritası (Story Map)")
    st.markdown("""
    <div class='card'><b>Nasıl dolduracaksın?</b><br/>
    Metindeki öykünün parçalarını tek tek yaz. Kısa yazman yeterli (1–2 cümle).</div>
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
        if st.button("🗂️ Öykü Haritasını Kaydet ve PUANLA (AI)"):
            filled = sum(1 for _, v in sm.items() if str(v).strip())
            st.session_state.story_map_filled = filled
            if filled < 3:
                st.warning("En az 3 alanı doldur (ör. kahraman, mekân, problem).")
            else:
                with st.spinner("AI rubrik puanı hesaplanıyor..."):
                    scores, total, reason = ai_score_story_map(metin, sm, st.session_state.get("sinif",""))

                ok = save_story_map_row(sm, scores, total, reason)
                if ok:
                    st.session_state.story_map_ai_scored = True
                    st.session_state.story_map_last_total = total
                    st.session_state.story_map_last_reason = reason
                    save_reading_process("STORY_MAP_SCORED", f"{total}/12 | {reason}", paragraf_no=None)
                    st.success(f"✅ Kaydedildi! AI Puan: {total}/12")
                    st.caption(f"Gerekçe: {reason}")

    with col_b:
        st.markdown("<div class='small-note'>AI Puan: ✅</div>" if st.session_state.story_map_ai_scored else "<div class='small-note'>AI Puan: ⏳</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("💬 Okuma Dostu'na Soru Sor (İsteğe bağlı)")
    user_q = st.chat_input("Metinle ilgili soru sorabilirsin…")
    if user_q:
        save_reading_process("CHAT_Q", user_q, paragraf_no=None)
        ai_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Sen ÖÖG öğretmenisin. Şu metne göre yardım et: {metin}"},
                {"role": "user", "content": user_q},
            ],
        )
        answer = ai_resp.choices[0].message.content
        save_reading_process("CHAT_A", answer, paragraf_no=None)
        st.session_state.chat_history.append({"q": user_q, "a": answer})

    for chat in st.session_state.chat_history:
        st.chat_message("user").write(chat["q"])
        st.chat_message("assistant").write(chat["a"])

    if st.button("Sorulara Geç ➜"):
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 6) QUESTIONS (METİNİ GÖSTER + İPUCU METNİ AÇAR)
# =========================================================
elif st.session_state.phase == "questions":
    sorular = st.session_state.activity.get("sorular", [])
    i = st.session_state.get("q_idx", 0)

    if not sorular:
        st.error("Sorular bulunamadı. SoruBankasi'nda bu metin için 6 soru olmalı.")
        st.stop()

    metin = st.session_state.activity.get("sade_metin", "")
    if "show_text_in_questions" not in st.session_state:
        st.session_state.show_text_in_questions = False

    colt1, colt2 = st.columns([3, 1])
    with colt1:
        st.markdown("<div class='small-note'>İstersen sorularda metni buradan açıp okuyabilirsin.</div>", unsafe_allow_html=True)
    with colt2:
        if st.button("📄 Metni Göster / Gizle"):
            st.session_state.show_text_in_questions = not st.session_state.show_text_in_questions

    if st.session_state.show_text_in_questions:
        with st.expander("📄 Metin", expanded=True):
            st.write(metin)

    st.divider()

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1} / {len(sorular)}")
        st.markdown(f"<div style='font-size:22px; margin-bottom:14px;'>{q.get('kok','')}</div>", unsafe_allow_html=True)

        colg1, colg2 = st.columns([2, 1])
        with colg1:
            st.markdown("<div class='small-note'>İstersen bu soruyu geçip en sonda geri dönebilirsin.</div>", unsafe_allow_html=True)
        with colg2:
            if st.button("⏭️ Geç (sonra dönerim)"):
                if i not in st.session_state.skipped:
                    st.session_state.skipped.append(i)
                save_reading_process("QUESTION_SKIPPED", f"Soru {i+1}", paragraf_no=None)
                st.session_state.q_idx = i + 1
                st.rerun()

        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q.get(opt,'')}", key=f"q_{i}_{opt}"):
                st.session_state.question_attempts[i] = st.session_state.question_attempts.get(i, 0) + 1
                is_correct = (opt == q.get("dogru"))
                st.session_state.correct_map[i] = 1 if is_correct else 0

                save_reading_process(
                    "ANSWER",
                    f"Soru {i+1} | secim={opt} | dogru={q.get('dogru')} | dogru_mu={is_correct} | deneme={st.session_state.question_attempts[i]}",
                    paragraf_no=None
                )

                if is_correct:
                    if st.session_state.hints_used_by_q.get(i, False):
                        st.session_state.correct_with_hint += 1
                    else:
                        st.session_state.correct_no_hint += 1

                    if i in st.session_state.skipped:
                        st.session_state.skipped = [x for x in st.session_state.skipped if x != i]

                    st.success("🌟 Doğru!")
                    st.session_state.q_idx = i + 1
                    st.rerun()
                else:
                    st.error("Tekrar dene!")

        if st.button("💡 İpucu Al", key=f"hint_{i}"):
            st.session_state.hints += 1
            st.session_state.hints_used_by_q[i] = True
            st.session_state.show_text_in_questions = True
            save_reading_process("HINT", f"Soru {i+1} | ipucu_alindi", paragraf_no=None)
            st.info("📌 Metni '📄 Metin' bölümünde açtım. Sorudaki anahtar kelimeleri metinde ara ve ilgili paragrafı tekrar oku.")

    else:
        if st.session_state.skipped:
            st.warning(f"{len(st.session_state.skipped)} soruyu geçtin. İstersen şimdi geri dönelim.")
            colr1, colr2 = st.columns(2)
            with colr1:
                if st.button("🔁 Geçilen Sorulara Dön"):
                    st.session_state.q_idx = st.session_state.skipped[0]
                    st.rerun()
            with colr2:
                if st.button("✅ Geçtiklerim kalsın, bitir"):
                    st.session_state.skipped = []
                    st.rerun()
        else:
            if not st.session_state.saved_perf:
                dogru = sum(st.session_state.correct_map.values())
                sure = round((time.time() - st.session_state.start_t) / 60, 2)
                wrongs = [str(idx + 1) for idx, v in st.session_state.correct_map.items() if v == 0]
                hatali = "Yanlış: " + ",".join(wrongs) if wrongs else "Hepsi doğru"

                # Planlama/izleme değişkenleri (Performans'a EK olarak sona yazıyoruz)
                tahmin = st.session_state.get("prediction", "")
                dikkat = "Evet" if st.session_state.get("attention_ok", False) else "Hayır"
                hiz = st.session_state.get("reading_speed", "")
                important_count = len(st.session_state.get("important_notes", []))
                prior = st.session_state.get("prior_knowledge", "")
                prior_var = 1 if prior.strip() else 0

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
                    "Evet", "Evet", 0, 0,

                    # ---- EK SÜTUNLAR (Sheet başlıklarına ekleyebilirsin) ----
                    tahmin,
                    dikkat,
                    hiz,
                    st.session_state.get("repeat_count", 0),
                    st.session_state.get("tts_count", 0),
                    st.session_state.get("reread_count", 0),
                    important_count,
                    prior_var,
                ]

                ok = append_row_safe("Performans", row)
                if ok:
                    save_reading_process("SESSION_END", f"Performans kaydedildi | dogru={dogru}/6 | sure={sure}dk", paragraf_no=None)
                    st.session_state.saved_perf = True
                    st.session_state.phase = "done"
                    st.rerun()

# =========================================================
# 7) DONE
# =========================================================
elif st.session_state.phase == "done":
    st.balloons()
    st.success("✅ Bugünkü çalışman kaydedildi!")

    sure = round((time.time() - st.session_state.get("start_t", time.time())) / 60, 2)
    dogru = sum(st.session_state.get("correct_map", {}).values())
    ipucu_toplam = st.session_state.get("hints", 0)
    ipucusuz_dogru = st.session_state.get("correct_no_hint", 0)
    ipuculu_dogru = st.session_state.get("correct_with_hint", 0)
    tekrar = st.session_state.get("repeat_count", 0)
    tts = st.session_state.get("tts_count", 0)
    reread = st.session_state.get("reread_count", 0)
    important_count = len(st.session_state.get("important_notes", []))
    prior_var = 1 if st.session_state.get("prior_knowledge", "").strip() else 0

    sm_filled = st.session_state.get("story_map_filled", 0)
    sm_total = st.session_state.get("story_map_last_total", None)

    st.subheader("📄 Öğrenci Raporu")
    st.markdown("<div class='report-card'>", unsafe_allow_html=True)
    st.markdown(f"""
**🕒 Okuma Süresi:** {sure} dakika  
**🏃 Seçilen Okuma Hızı:** {st.session_state.get("reading_speed","")}  
**✅ Dikkat Onayı:** {"Evet" if st.session_state.get("attention_ok", False) else "Hayır"}  
**💭 Tahmin:** {st.session_state.get("prediction","") or "—"}  

**🔁 İzleme Davranışları**
- Toplam tekrar (dinleme + tekrar okuma): {tekrar}
- Dinleme (TTS): {tts}
- Tekrar okuma: {reread}
- Önemli cümle kaydı: {important_count}
- Ön bilgi yazdı mı: {prior_var}

**❓ Sorular**
- Toplam soru: 6
- Doğru: {dogru}
- İpucu toplam: {ipucu_toplam}
- İpucu almadan doğru: {ipucusuz_dogru}
- İpucu aldıktan sonra doğru: {ipuculu_dogru}

**🗺️ Öykü Haritası**
- Doluluk: {sm_filled}/6
- AI Puanı: {f"{sm_total}/12" if sm_total is not None else "—"}
""")
    if st.session_state.get("story_map_last_reason", ""):
        st.caption(f"AI kısa gerekçe: {st.session_state.story_map_last_reason}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yeni Metin"):
            st.session_state.phase = "setup"
            reset_activity_states()
            st.rerun()
    with c2:
        if st.button("Çıkış"):
            st.session_state.clear()
            st.rerun()
