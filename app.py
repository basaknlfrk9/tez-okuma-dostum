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
# ZORUNLU DEBUG (HER KOŞULDA GÖRÜNÜR)
# =========================================================
st.set_page_config(page_title="Okuma Dostum", layout="wide")

st.error("🔴 DEBUG BAR: BU YAZIYI GÖRMÜYORSAN YANLIŞ DOSYA ÇALIŞIYOR")

st.write("Secrets kontrol:",
         "OPENAI_API_KEY" in st.secrets,
         "GSHEET_URL" in st.secrets,
         "GSHEETS" in st.secrets)

# =========================================================
# GOOGLE SHEETS TEST (EN ÜSTTE)
# =========================================================
def test_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    info = dict(st.secrets["GSHEETS"])
    if "\\n" in info.get("private_key", ""):
        info["private_key"] = info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(info, scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(st.secrets["GSHEET_URL"])

    st.write("📄 Sheet sekmeleri:", [w.title for w in sh.worksheets()])

    ws = sh.worksheet("Performans")
    ws.append_row(
        ["TEST", "TEST", "TEST", 0.1, "5", "%0", 6, 0, "Analiz",
         "Metin_1", 0, "Evet", "Evet", 0, 0],
        value_input_option="USER_ENTERED"
    )

if st.button("🧪 GOOGLE SHEETS TEST (1 satır yaz)"):
    try:
        test_sheets()
        st.success("✅ GOOGLE SHEETS YAZDI")
    except Exception:
        st.error("❌ GOOGLE SHEETS HATASI (TAM)")
        st.code(traceback.format_exc())

st.divider()

# =========================================================
# OPENAI
# =========================================================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =========================================================
# SESSION
# =========================================================
if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# =========================================================
# 1) GİRİŞ
# =========================================================
if st.session_state.phase == "auth":
    st.title("🌟 Okuma Dostum")

    user = st.text_input("Ad Soyad")
    sinif = st.selectbox("Sınıf", ["5", "6", "7", "8"])

    if st.button("Başla") and user:
        st.session_state.user = user
        st.session_state.sinif = sinif
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.login_time = datetime.now(
            ZoneInfo("Europe/Istanbul")
        ).strftime("%d.%m.%Y %H:%M")
        st.session_state.phase = "setup"
        st.rerun()

# =========================================================
# 2) METİN YÜKLE
# =========================================================
elif st.session_state.phase == "setup":
    st.header("📄 Metin Yükle")

    metin_id = st.text_input("Metin ID", "Metin_1")
    up = st.file_uploader("PDF yükle", type="pdf")
    txt = st.text_area("Veya metni yapıştır")

    if st.button("Hazırla") and (up or txt):
        raw = txt.strip()

        if up:
            reader = PdfReader(up)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])

        prompt = """
        Metni sadeleştir ve 6 soru üret.
        JSON format:
        {
          "sade_metin": "...",
          "sorular": [
            {"kok":"...","A":"...","B":"...","C":"...","dogru":"A","ipucu":"..."}
          ]
        }
        """

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw}
            ],
            response_format={"type": "json_object"}
        )

        st.session_state.activity = json.loads(
            resp.choices[0].message.content
        )
        st.session_state.metin_id = metin_id
        st.session_state.q_idx = 0
        st.session_state.correct = 0
        st.session_state.start_t = time.time()
        st.session_state.phase = "questions"
        st.rerun()

# =========================================================
# 3) SORULAR
# =========================================================
elif st.session_state.phase == "questions":
    act = st.session_state.activity
    sorular = act["sorular"]
    i = st.session_state.q_idx

    if i < len(sorular):
        q = sorular[i]
        st.subheader(f"Soru {i+1}")

        st.write(q["kok"])

        for opt in ["A", "B", "C"]:
            if st.button(f"{opt}) {q[opt]}"):
                if opt == q["dogru"]:
                    st.session_state.correct += 1
                st.session_state.q_idx += 1
                st.rerun()

    else:
        st.warning("🟡 KAYIT AŞAMASINA GELDİ")

        sure = round((time.time() - st.session_state.start_t) / 60, 2)

        row = [
            st.session_state.session_id,
            st.session_state.user,
            st.session_state.login_time,
            sure,
            st.session_state.sinif,
            f"%{round(st.session_state.correct/6*100,1)}",
            6,
            st.session_state.correct,
            "Analiz",
            st.session_state.metin_id,
            0,
            "Evet",
            "Evet",
            0,
            0
        ]

        st.write("📌 Yazılacak satır:", row)

        try:
            test_sheets()
            st.success("🎉 KAYIT TAMAM")
            st.session_state.phase = "done"
            st.rerun()
        except Exception:
            st.error("❌ KAYIT HATASI")
            st.code(traceback.format_exc())

# =========================================================
# 4) BİTTİ
# =========================================================
elif st.session_state.phase == "done":
    st.balloons()
    st.success("Bitti 🎉")
    if st.button("Yeniden"):
        st.session_state.clear()
        st.rerun()
