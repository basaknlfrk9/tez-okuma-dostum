import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Tez Okuma Dostum")

# --- Google Sheets bağlantısı ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(st.secrets["GSHEETS_CREDENTIALS"])

credentials = Credentials.from_service_account_info(
    creds_dict,
    scopes=scope
)

gc = gspread.authorize(credentials)

sheet = gc.open_by_key(
    st.secrets["SPREADSHEET_ID"]
).sheet1

st.success("✅ Google Sheets bağlantısı başarılı")

# --- Test yazma ---
if st.button("Test veri yaz"):
    sheet.append_row(["Başak", "Test", "Çalışıyor"])
    st.success("🎉 Veri eklendi")
