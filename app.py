import streamlit as st
from openai import OpenAI
import PyPDF2
import pandas as pd
import os
import json
from datetime import datetime

st.set_page_config(page_title="Tez Asistanı", layout="wide")

excel_file = "kullanicilar.xlsx"

if not os.path.exists(excel_file):
    df = pd.DataFrame(columns=["Kullanici Adi", "Tarih"])
    df.to_excel(excel_file, index=False)


def kullanici_kaydet(kullanici_adi):
    try:
        df = pd.read_excel(excel_file)
        yeni_kayit = pd.DataFrame(
            [[kullanici_adi, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]],
            columns=["Kullanici Adi", "Tarih"]
        )
        df = pd.concat([df, yeni_kayit], ignore_index=True)
        df.to_excel(excel_file, index=False)
    except Exception as e:
        st.error(f"Excel Hatasi: {e}")


def gecmis_yukle(kullanici_adi):
    dosya_adi = f"{kullanici_adi}_chat.json"
    if os.path.exists(dosya_adi):
        with open(dosya_adi, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def gecmis_kaydet(kullanici_adi, mesajlar):
    dosya_adi = f"{kullanici_adi}_chat.json"
    with open(dosya_adi, "w", encoding="utf-8") as f:
        json.dump(mesajlar, f, ensure_ascii=False, indent=4)


if "current_user" not in st.session_state:
    st.title("Giris Yapin")
    user_input = st.text_input("Adinizi girin:")
else:
    kullanici = st.session_state.current_user
    st.sidebar.success(f"Hosgeldin, {kullanici}")
