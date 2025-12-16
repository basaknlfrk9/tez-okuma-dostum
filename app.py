import streamlit as st from openai import OpenAI import os import json from pypdf import PdfReader from docx import Document

st.set_page_config(page_title="Tez Okuma Dostum", page_icon="🎓", layout="wide")

st.sidebar.title("🎓 Öğrenci Girişi") kullanici_adi = st.sidebar.text_input("Adınız Soyadınız:", placeholder="Örn: Elif Polat")

def gecmisi_yukle(isim): dosya_adi = f"{isim.replace(' ', '_').lower()}_chat.json" if os.path.exists(dosya_adi): with open(dosya_adi, "r", encoding="utf-8") as f: return json.load(f) return []

def gecmisi_kaydet(isim, mesajlar): dosya_adi = f"{isim.replace(' ', '_').lower()}_chat.json" with open(dosya_adi, "w", encoding="utf-8") as f: json.dump(mesajlar, f, ensure_ascii=False, indent=4)

if not kullanici_adi: st.info("👋 Lütfen başlamak için sol taraftan adınızı girin.") st.stop()

if "OPENAI_API_KEY" not in st.secrets: st.error("Lütfen API anahtarınızı ekleyin.") st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title(f"Hoş Geldin, {kullanici_adi}! 👋")

if "messages" not in st.session_state: eski_kayitlar = gecmisi_yukle(kullanici_adi) if eski_kayitlar: st.session_state.messages = eski_kayitlar else: st.session_state.messages = [] st.session_state.messages.append({"role": "assistant", "content": "Merhaba! Nasıl yardımcı olabilirim?"})

uploaded_file = st.sidebar.file_uploader("Dosya Yükle", type=["pdf", "docx", "txt"]) context = ""

if uploaded_file: try: if uploaded_file.name.endswith(".pdf"): reader = PdfReader(uploaded_file) for page in reader.pages: context += page.extract_text() elif uploaded_file.name.endswith(".docx"): doc = Document(uploaded_file) for para in doc.paragraphs: context += para.text elif uploaded_file.name.endswith(".txt"): context = uploaded_file.read().decode("utf-8") st.sidebar.success("Dosya analiz edildi!") except: st.sidebar.error("Dosya okunamadı.")

for msg in st.session_state.messages: with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Mesajını yaz..."): st.session_state.messages.append({"role": "user", "content": prompt}) with st.chat_message("user"): st.markdown(prompt)
