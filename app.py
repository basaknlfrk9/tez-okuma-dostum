import streamlit as st
from PyPDF2 import PdfReader
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re, json, uuid, time

# =========================================================
# OKUMA DOSTUM — HATA AYIKLAMA VE VERİ KAYIT MODÜLÜ
# =========================================================

# 1. GÜVENLİ ANAHTAR KONTROLÜ
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except KeyError:
    st.error("❌ HATA: OpenAI API Anahtarı bulunamadı! Lütfen Streamlit Secrets ayarlarını kontrol edin.")
    st.stop()

# 2. SHEETS BAĞLANTI FONKSİYONU
def save_data(data_row):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        # Secrets içindeki GSHEETS yapısını kontrol et
        if "GSHEETS" not in st.secrets:
            st.error("❌ HATA: 'GSHEETS' anahtarı Secrets kısmında tanımlı değil!")
            return False
            
        creds = Credentials.from_service_account_info(st.secrets["GSHEETS"], scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(st.secrets["GSHEET_URL"])
        
        # Sayfa adını kontrol et (Performans mı?)
        try:
            ws = sh.worksheet("Performans")
        except:
            st.warning("⚠️ 'Performans' sayfası bulunamadı, ilk sayfaya yazılıyor.")
            ws = sh.get_worksheet(0)
            
        ws.append_row(data_row)
        return True
    except Exception as e:
        st.error(f"❌ KAYIT HATASI: {str(e)}")
        return False

# Uygulama Başlangıcı
if "phase" not in st.session_state:
    st.session_state.phase = "auth"

# ... (Buradan sonrası önceki akış kodlarıyla aynıdır)
# Sadece kayıt anında save_data(final_row) fonksiyonunu çağırın.
