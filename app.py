import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from openai import OpenAI
import tempfile
from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
from io import BytesIO
import re
import json
import uuid
import time

# =========================================================
# OKUMA DOSTUM — MEB Metinleri + ÖÖG + Sunuş Yoluyla Öğretim
# - Metin/PDF: öğretmen ekler
# - Öğrenci: parça parça okur, A/B/C sorular
# - Ölçme: doğruluk, süre, ipucu, TTS, mic
# - Sheets: Sohbet (ayrıntı) + Performans (özet)
# =========================================================

st.set_page_config(page_title="Okuma Dostum", layout="wide", initial_sidebar_state="expanded")

# ------------------ ÖÖG DOSTU CSS ------------------
st.markdown(
    """
<style>
html, body, [class*="css"] { font-size: 20px !important; }
p, li, div, span { line-height: 1.9 !important; }
.stChatMessage p { font-size: 20px !important; line-height: 1.9 !important; }
.stTextInput input, .stTextArea textarea {
  font-size: 20px !important; line-height: 1.9 !important; padding: 14px 14px !important;
}
.stTextArea textarea::placeholder { font-size: 18px !important; opacity: .65; }
.stButton button{ font-size: 18px !important; border-radius: 16px !important; padding: 10px 14px !important; }
.stMarkdown { word-spacing: 0.16em !important; letter-spacing: 0.02em !important; }
.block-container { padding-top: 2rem; padding-bottom: 2.0rem; max-width: none; }
.card{
  border:1px solid rgba(0,0,0,.12);
  border-radius:18px; padding:16px 18px; margin:12px 0;
  background: rgba(255,255,255,.92);
}
.badge{
  display:inline-block; padding:6px 12px; border-radius:999px;
  border:1px solid rgba(0,0,0,.12); font-size:16px; opacity:.85; margin-bottom:10px;
}
.smallhint{ font-size: 14px; opacity: .7; }
hr { margin: 0.8rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------ OPENAI CLIENT ------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ------------------ GOOGLE SHEETS ------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
gc = gspread.authorize(credentials)
workbook = gc.open_by_url(st.secrets["GSHEET_URL"])

# Sheets: Sohbet + Performans
try:
    chat_sheet = workbook.worksheet("Sohbet")
except WorksheetNotFound:
    chat_sheet = workbook.add_worksheet(title="Sohbet", rows=5000, cols=25)

try:
    perf_sheet = workbook.worksheet("Performans")
except WorksheetNotFound:
    perf_sheet = workbook.add_worksheet(title="Performans", rows=5000, cols=25)

SOHBET_HEADERS = [
    "OturumID", "Kullanici", "Zaman",
    "SinifDuzeyi", "MetinKaynak", "MetinID",
    "Rol", "Mesaj",
    "SoruID", "SoruTuru", "SoruKok",
    "A", "B", "C",
    "Secilen", "DogruSecenek", "DogruMu",
    "IpucuSayisi", "SureSn", "TTS", "Mic"
]

PERF_HEADERS = [
    "OturumID", "Kullanici", "TarihSaat",
    "SinifDuzeyi", "MetinKaynak", "MetinID",
    "ToplamSoru", "DogruSayi", "DogrulukYuzde",
    "OrtalamaSureSn", "ToplamIpucu",
    "AnaFikirDogruMu", "CikarimDogruMu",
    "TTS_Kullanim", "Mic_Kullanim"
]

def ensure_headers(sheet, headers):
    try:
        first = sheet.row_values(1)
        if first != headers:
            if not first:
                sheet.append_row(headers)
            else:
                # başlık farklıysa zorlamayalım; ama kullanıcıya da hata vermeyelim
                pass
    except Exception:
        pass

ensure_headers(chat_sheet, SOHBET_HEADERS)
ensure_headers(perf_sheet, PERF_HEADERS)

def now_tr_str():
    return datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M:%S")

def sheet_append_safe(sheet, row):
    try:
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Sheet yazma hatası: {e}")

def log_chat_row(**kw):
    # boşları güvenli doldur
    row = [
        kw.get("OturumID",""),
        kw.get("Kullanici",""),
        kw.get("Zaman",""),
        kw.get("SinifDuzeyi",""),
        kw.get("MetinKaynak",""),
        kw.get("MetinID",""),
        kw.get("Rol",""),
        kw.get("Mesaj",""),
        kw.get("SoruID",""),
        kw.get("SoruTuru",""),
        kw.get("SoruKok",""),
        kw.get("A",""),
        kw.get("B",""),
        kw.get("C",""),
        kw.get("Secilen",""),
        kw.get("DogruSecenek",""),
        kw.get("DogruMu",""),
        kw.get("IpucuSayisi",""),
        kw.get("SureSn",""),
        kw.get("TTS",""),
        kw.get("Mic",""),
    ]
    sheet_append_safe(chat_sheet, row)

def log_perf_row(**kw):
    row = [
        kw.get("OturumID",""),
        kw.get("Kullanici",""),
        kw.get("TarihSaat",""),
        kw.get("SinifDuzeyi",""),
        kw.get("MetinKaynak",""),
        kw.get("MetinID",""),
        kw.get("ToplamSoru",""),
        kw.get("DogruSayi",""),
        kw.get("DogrulukYuzde",""),
        kw.get("OrtalamaSureSn",""),
        kw.get("ToplamIpucu",""),
        kw.get("AnaFikirDogruMu",""),
        kw.get("CikarimDogruMu",""),
        kw.get("TTS_Kullanim",""),
        kw.get("Mic_Kullanim",""),
    ]
    sheet_append_safe(perf_sheet, row)

# ------------------ TTS (noktalama okumasını azalt) ------------------
def clean_for_tts(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"[#>\[\]\(\)\{\}_`~^=|\\/@]", " ", t)
    t = re.sub(r"[:;,.!?…“”\"'’\-–—]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tts_bytes(text: str) -> bytes:
    safe = clean_for_tts(text)
    if not safe:
        safe = "Hazırım."
    if len(safe) > 1400:
        safe = safe[:1400] + " ..."
    mp3_fp = BytesIO()
    gTTS(safe, lang="tr").write_to_fp(mp3_fp)
    return mp3_fp.getvalue()

# ------------------ MODEL: MEB soru paketi (JSON) ------------------
def system_prompt_meb_json():
    return """
Sen, özel öğrenme güçlüğü (ÖÖG) olan ortaokul öğrencisi için okuma yardımı yapan bir yardımcı öğretmensin.
Öğretim stratejin: SUNUŞ YOLUYLA ÖĞRETİM (Ausubel).

HEDEF:
- Metni parça parça okut (2-4 parça).
- Her parçada 2 kısa kontrol sorusu (çok kısa, A/B/C değil; evet/hayır veya 1 cümlelik).
- Sonra MEB tarzı sorular sor: A/B/C seçmeli.
- Yazma yükünü azalt: kısa, net, seçenekli.

KURALLAR:
- Uzun paragraf yok.
- Basit kelime, kısa cümle.
- A/B/C seçenekleri birbirine yakın ve anlaşılır olsun.
- Çeldirici (yanlış seçenek) çok zor olmasın.
- Metin yoksa kısa bir metin üret.

ÇIKTI: SADECE JSON. Başka hiçbir şey yazma.

JSON ŞEMASI:
{
  "acilis": "1-2 cümle (merak + hedef)",
  "kelime_destek": [{"kelime":"", "anlam":""}, ... (en fazla 3)],
  "parcalar": [
    {"metin":"kısa parça", "kontrol1":"", "kontrol2":""}
  ],
  "sorular": [
    {
      "id":"Q1",
      "tur":"bilgi|cikarim|ana_fikir|baslik|kelime",
      "kok":"soru kökü",
      "A":"", "B":"", "C":"",
      "dogru":"A",
      "aciklama":"1 kısa cümle",
      "ipucu":"1 kısa ipucu"
    }
  ],
  "kisa_tekrar":"1 cümle (özet)"
}

SORU PAKETİ: Tam 6 soru üret:
- 2 bilgi
- 1 cikarim
- 1 kelime
- 1 ana_fikir
- 1 baslik
"""

def safe_json_load(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            return json.loads(m.group(0))
        return {}

def ask_meb_activity(source_text: str) -> dict:
    user_prompt = f"KAYNAK METİN:\n{source_text}\n\nMetni 2-4 parçaya böl ve şemaya göre JSON üret."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt_meb_json()},
            {"role": "user", "content": user_prompt},
        ],
    )
    d = safe_json_load(resp.choices[0].message.content)
    # default güvenlik
    d.setdefault("acilis", "Bugün metni birlikte okuyacağız. Sonra sorularla anlayacağız.")
    d.setdefault("kelime_destek", [])
    d.setdefault("parcalar", [])
    d.setdefault("sorular", [])
    d.setdefault("kisa_tekrar", "Kısaca: Metnin ana fikrini bulduk ve soruları çözdük.")
    # soruları 6 ile sınırla
    if isinstance(d.get("sorular"), list):
        d["sorular"] = d["sorular"][:6]
    else:
        d["sorular"] = []
    return d

# ------------------ Metin alma ------------------
def read_pdf_text(pdf_file) -> str:
    try:
        reader = PdfReader(pdf_file)
        txt_all = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                txt_all += t + "\n"
        return txt_all.strip()
    except Exception:
        return ""

def build_source_text(pdf_text: str, extra_text: str) -> str:
    src = ""
    if pdf_text.strip():
        src += pdf_text.strip() + "\n"
    if extra_text.strip():
        src += extra_text.strip() + "\n"
    return src.strip()

# ------------------ UI helpers ------------------
def card(title: str, body_md: str):
    st.markdown(
        f"""
<div class="card">
  <div class="badge">{title}</div>
  <div>{body_md}</div>
</div>
""",
        unsafe_allow_html=True,
    )

# =========================================================
# 1) GİRİŞ EKRANI
# =========================================================
if "user" not in st.session_state:
    st.markdown(
        """
        <div style="text-align:center; margin-top:60px;">
            <div style="font-size:52px; font-weight:900;">📚 Okuma Dostum</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:12px; margin-top:30px;">
            <div style="font-size:30px;">👋</div>
            <div style="font-size:26px; font-weight:800;">Hoş geldiniz</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    isim = st.text_input("Adını yaz", placeholder="Örn: Ali")

    # Sınıf düzeyi seçimi (tez için önemli)
    sinif = st.selectbox("Sınıfını seç", ["5", "6", "7", "8"], index=0)

    if st.button("Giriş Yap", use_container_width=True) and isim.strip():
        st.session_state.user = isim.strip()
        st.session_state.sinif = sinif
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.pdf_text = ""
        st.session_state.extra_text = ""
        st.session_state.activity = None
        st.session_state.q_index = 0
        st.session_state.q_started_at = None
        st.session_state.hint_used = 0
        st.session_state.tts_used = 0
        st.session_state.mic_used = 0
        st.session_state.correct_map = {}  # qid -> 1/0
        st.session_state.type_correct = {"ana_fikir": None, "cikarim": None}
        st.session_state.total_time = 0.0
        st.session_state.total_ipucu = 0
        st.session_state.last_bot_text = ""
        st.session_state["draft"] = ""
        st.rerun()

    with st.expander("❓ Chatbot nasıl kullanılır?"):
        st.markdown(
            """
- Öğretmen metni ekler (PDF / metin).
- Metni parça parça okuruz.
- Sonra MEB tarzı A/B/C sorular çözeriz.
- 🎤 ile konuşabilirsin.
- 🔊 ile dinleyebilirsin.
"""
        )
    st.stop()

# =========================================================
# 2) ÜST BAŞLIK (tek odak)
# =========================================================
st.markdown(
    f"""
<div style="text-align:center; margin-bottom:10px;">
  <div style="font-size:44px; font-weight:900;">📚 Okuma Dostum</div>
  <div style="font-size:18px; opacity:0.7;">{st.session_state.user} • {st.session_state.sinif}. Sınıf</div>
</div>
""",
    unsafe_allow_html=True,
)

col_exit = st.columns([8, 2])[1]
with col_exit:
    if st.button("Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")

# =========================================================
# 3) SOL PANEL (öğretmen alanı)
# =========================================================
with st.sidebar:
    with st.expander("📄 PDF ekle", expanded=False):
        pdf_file = st.file_uploader("PDF seç", type="pdf", key="pdf_uploader")
        if pdf_file is not None:
            st.session_state.pdf_text = read_pdf_text(pdf_file)
            if st.session_state.pdf_text:
                st.success("PDF yüklendi ✔️")
            else:
                st.warning("PDF metni okunamadı (tarama PDF olabilir).")

    with st.expander("📝 Metin ekle", expanded=False):
        st.session_state.extra_text = st.text_area("Metni buraya yapıştır", height=220, key="extra_text_area")

    with st.expander("🏷️ Metin bilgisi (tez için)", expanded=False):
        st.session_state.metin_kaynak = st.selectbox("Metin Kaynak", ["MEB", "Diğer"], index=0)
        st.session_state.metin_id = st.text_input("Metin ID", placeholder="Örn: 6.sınıf Ünite2 Metin3")

pdf_text = st.session_state.get("pdf_text", "")
extra_text = st.session_state.get("extra_text", "")
metin_kaynak = st.session_state.get("metin_kaynak", "MEB")
metin_id = st.session_state.get("metin_id", "")

# =========================================================
# 4) Sohbet geçmişi (kısa tutuyoruz)
# =========================================================
for m in st.session_state.get("messages", []):
    with st.chat_message(m["role"]):
        st.write(m["content"])

# =========================================================
# 5) Aktivite başlat (MEB okuma etkinliği)
# =========================================================
def start_activity():
    source_text = build_source_text(pdf_text, extra_text)
    if not source_text:
        source_text = "Kısa bir bilgilendirici metin üret ve okuma etkinliği yap."

    # modelden aktivite al
    activity = ask_meb_activity(source_text)

    st.session_state.activity = activity
    st.session_state.q_index = 0
    st.session_state.q_started_at = time.time()
    st.session_state.hint_used = 0
    st.session_state.correct_map = {}
    st.session_state.type_correct = {"ana_fikir": None, "cikarim": None}
    st.session_state.total_time = 0.0
    st.session_state.total_ipucu = 0

    # sohbet log (başlangıç)
    st.session_state.messages.append({"role": "assistant", "content": activity.get("acilis", "")})
    st.session_state.last_bot_text = activity.get("acilis", "")

    log_chat_row(
        OturumID=st.session_state.session_id,
        Kullanici=st.session_state.user,
        Zaman=now_tr_str(),
        SinifDuzeyi=st.session_state.sinif,
        MetinKaynak=metin_kaynak,
        MetinID=metin_id,
        Rol="assistant",
        Mesaj=activity.get("acilis",""),
        TTS="0",
        Mic="0",
    )

# =========================================================
# 6) Aktivite göster (parçalar + aktif soru)
# =========================================================
def render_activity(activity: dict):
    # kelime desteği
    kel = activity.get("kelime_destek", [])
    if kel:
        lines = "<br>".join([f"• <b>{k.get('kelime','')}</b>: {k.get('anlam','')}" for k in kel[:3]])
        card("Kelime desteği", lines)

    # okuma parçaları (hepsini bir kartta, kısa)
    parcalar = activity.get("parcalar", [])
    if parcalar:
        body = ""
        for i, p in enumerate(parcalar[:4], start=1):
            body += f"<b>Parça {i}:</b> {p.get('metin','')}<br>"
            body += f"• {p.get('kontrol1','')}<br>"
            body += f"• {p.get('kontrol2','')}<br><br>"
        card("Okuma (parça parça)", body)

    # aktif soru (tek soru!)
    sorular = activity.get("sorular", [])
    if not sorular:
        card("Soru", "Soru üretilemedi. Lütfen metni kontrol et.")
        return

    idx = st.session_state.q_index
    if idx >= len(sorular):
        # bitiş özeti
        toplam = len(sorular)
        dogru = sum(int(v) for v in st.session_state.correct_map.values()) if st.session_state.correct_map else 0
        yuzde = round((dogru / toplam) * 100, 1) if toplam else 0.0
        ort_sure = round(st.session_state.total_time / toplam, 2) if toplam else 0.0

        card("Bitti ✅", f"Toplam soru: <b>{toplam}</b><br>Doğru: <b>{dogru}</b><br>Başarı: <b>%{yuzde}</b><br>Ortalama süre: <b>{ort_sure} sn</b>")
        card("Kısa tekrar", activity.get("kisa_tekrar",""))

        # performans sheet’e yaz
        log_perf_row(
            OturumID=st.session_state.session_id,
            Kullanici=st.session_state.user,
            TarihSaat=now_tr_str(),
            SinifDuzeyi=st.session_state.sinif,
            MetinKaynak=metin_kaynak,
            MetinID=metin_id,
            ToplamSoru=str(toplam),
            DogruSayi=str(dogru),
            DogrulukYuzde=str(yuzde),
            OrtalamaSureSn=str(ort_sure),
            ToplamIpucu=str(st.session_state.total_ipucu),
            AnaFikirDogruMu=str(st.session_state.type_correct.get("ana_fikir")),
            CikarimDogruMu=str(st.session_state.type_correct.get("cikarim")),
            TTS_Kullanim=str(st.session_state.tts_used),
            Mic_Kullanim=str(st.session_state.mic_used),
        )
        return

    q = sorular[idx]
    qid = q.get("id", f"Q{idx+1}")
    tur = q.get("tur", "")
    kok = q.get("kok", "")
    A, B, C = q.get("A",""), q.get("B",""), q.get("C","")
    dogru = q.get("dogru", "A")
    aciklama = q.get("aciklama", "")
    ipucu = q.get("ipucu", "")

    card("Soru", f"<b>{idx+1}/{len(sorular)}</b> • <b>{kok}</b><br><br>A) {A}<br>B) {B}<br>C) {C}")

    # ipucu butonu
    colh1, colh2 = st.columns([1, 3])
    with colh1:
        if st.button("💡 İpucu", use_container_width=True, key=f"hint_{qid}"):
            st.session_state.hint_used += 1
            st.session_state.total_ipucu += 1
            st.info(ipucu if ipucu else "Metne dön ve ana fikri düşün.")

    # seçenekler
    colA, colB, colC = st.columns(3)
    chosen = None
    with colA:
        if st.button("A", use_container_width=True, key=f"A_{qid}"):
            chosen = "A"
    with colB:
        if st.button("B", use_container_width=True, key=f"B_{qid}"):
            chosen = "B"
    with colC:
        if st.button("C", use_container_width=True, key=f"C_{qid}"):
            chosen = "C"

    if chosen:
        # süre
        started = st.session_state.q_started_at or time.time()
        sure = round(time.time() - started, 2)
        st.session_state.total_time += sure

        dogru_mu = 1 if chosen == dogru else 0
        st.session_state.correct_map[qid] = dogru_mu

        # ana_fikir / cikarim özel takip
        if tur == "ana_fikir":
            st.session_state.type_correct["ana_fikir"] = dogru_mu
        if tur == "cikarim":
            st.session_state.type_correct["cikarim"] = dogru_mu

        # geri bildirim (ÖÖG: kısa)
        if dogru_mu:
            st.success("Doğru ✅")
        else:
            st.warning(f"Yanlış. Doğru cevap: {dogru}")
        if aciklama:
            st.caption(aciklama)

        # Sheets log (soru satırı)
        log_chat_row(
            OturumID=st.session_state.session_id,
            Kullanici=st.session_state.user,
            Zaman=now_tr_str(),
            SinifDuzeyi=st.session_state.sinif,
            MetinKaynak=metin_kaynak,
            MetinID=metin_id,
            Rol="user",
            Mesaj="(A/B/C cevap)",
            SoruID=qid,
            SoruTuru=tur,
            SoruKok=kok,
            A=A, B=B, C=C,
            Secilen=chosen,
            DogruSecenek=dogru,
            DogruMu=str(dogru_mu),
            IpucuSayisi=str(st.session_state.hint_used),
            SureSn=str(sure),
            TTS=str(st.session_state.tts_used),
            Mic=str(st.session_state.mic_used),
        )

        # sonraki soruya geç
        st.session_state.q_index += 1
        st.session_state.q_started_at = time.time()
        st.session_state.hint_used = 0
        st.rerun()

# =========================================================
# 7) ANA KONTROL: Aktivite var mı?
# =========================================================
if st.session_state.activity:
    with st.chat_message("assistant"):
        render_activity(st.session_state.activity)
else:
    # öğrenciye kısa yönlendirme
    with st.chat_message("assistant"):
        card("Başlangıç", "Önce öğretmen PDF veya metin ekleyebilir. Sonra <b>Başla</b> butonuna bas.")

# =========================================================
# 8) ALT BAR: Mesaj + 🎤 + 🔊 + Başla
# - draft sıfırlama burada kesin çözülür
# =========================================================
c_msg, c_mic, c_audio, c_start = st.columns([8, 1.2, 1.2, 2.2])

with c_msg:
    st.text_area(
        "",
        placeholder="İstersen buraya yaz: (Örn: Bu metni birlikte okuyalım)",
        height=70,
        key="draft",
    )

with c_mic:
    with st.popover("🎤", use_container_width=True):
        st.markdown('<div class="smallhint">Konuş → durdur</div>', unsafe_allow_html=True)
        audio_bytes = audio_recorder(
            text="Konuş",
            pause_threshold=1.8,
            sample_rate=16000,
            key="mic_main",
        )
        if audio_bytes:
            st.session_state.mic_used = 1
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                with open(tmp_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="tr",
                    )
                mic_text = (transcript.text or "").strip()
                if mic_text:
                    # sohbet log
                    st.session_state.messages.append({"role": "user", "content": mic_text})
                    log_chat_row(
                        OturumID=st.session_state.session_id,
                        Kullanici=st.session_state.user,
                        Zaman=now_tr_str(),
                        SinifDuzeyi=st.session_state.sinif,
                        MetinKaynak=metin_kaynak,
                        MetinID=metin_id,
                        Rol="user",
                        Mesaj=mic_text,
                        Mic="1"
                    )
                    # draft'a yaz, ama hemen sıfırlanacak (başla deyince)
                    st.session_state["draft"] = mic_text
                    st.success("Yazıya çevrildi ✔️")
            except Exception as e:
                st.error(f"Ses yazıya çevrilemedi: {e}")

with c_audio:
    if st.button("🔊", use_container_width=True):
        t = st.session_state.get("last_bot_text", "")
        if t.strip():
            st.session_state.tts_used = 1
            st.audio(tts_bytes(t), format="audio/mp3")
        else:
            st.warning("Dinlenecek bir şey yok.")

with c_start:
    if st.button("Başla", use_container_width=True):
        # (İsteğe bağlı) öğrenci/öğretmen mesajı log
        user_note = st.session_state.get("draft","").strip()
        if user_note:
            st.session_state.messages.append({"role": "user", "content": user_note})
            log_chat_row(
                OturumID=st.session_state.session_id,
                Kullanici=st.session_state.user,
                Zaman=now_tr_str(),
                SinifDuzeyi=st.session_state.sinif,
                MetinKaynak=metin_kaynak,
                MetinID=metin_id,
                Rol="user",
                Mesaj=user_note,
                TTS=str(st.session_state.tts_used),
                Mic=str(st.session_state.mic_used),
            )

        # Aktiviteyi başlat
        start_activity()

        # ✅ EN ÖNEMLİ: soru kutusunu sıfırla
        st.session_state["draft"] = ""

        st.rerun()
