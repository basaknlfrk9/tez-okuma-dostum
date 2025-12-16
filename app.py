import streamlit as st
from openai import OpenAI
import datetime
import csv
import os
from pypdf import PdfReader
import docx

# ==========================================
# 1. AYARLAR
# ==========================================
# Kendi API anahtarını tırnak içine yaz:
# Anahtarı gizli kasadan (secrets) al
api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)


st.set_page_config(page_title="Okuma Dostum", layout="wide")

# ==========================================
# 2. DOSYA OKUMA FONKSİYONLARI (YENİ)
# ==========================================
def metin_oku(yuklenen_dosya):
    if yuklenen_dosya.type == "text/plain":
        # TXT Dosyası
        return str(yuklenen_dosya.read(), "utf-8")
    elif yuklenen_dosya.type == "application/pdf":
        # PDF Dosyası
        pdf_okuyucu = PdfReader(yuklenen_dosya)
        metin = ""
        for sayfa in pdf_okuyucu.pages:
            metin += sayfa.extract_text()
        return metin
    elif yuklenen_dosya.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        # Word Dosyası (docx)
        doc = docx.Document(yuklenen_dosya)
        metin = ""
        for paragraf in doc.paragraphs:
            metin += paragraf.text + "\n"
        return metin
    return ""

# ==========================================
# 3. KAYIT TUTMA (LOGLAMA - DÜZELTİLMİŞ)
# ==========================================
def veriyi_kaydet(ogrenci_adi, metin_konusu, soru, cevap):
    dosya_adi = "tez_verileri.csv"
    zaman = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    dosya_yok = not os.path.exists(dosya_adi)
    
    # Excel düzeltmesi (utf-8-sig ve noktalı virgül) burada aktif
    with open(dosya_adi, mode='a', newline='', encoding='utf-8-sig') as f:
        yazici = csv.writer(f, delimiter=';')
        if dosya_yok:
            yazici.writerow(["Zaman", "Öğrenci Adı", "Metin Konusu", "Öğrenci Sorusu", "Botun Cevabı"])
        yazici.writerow([zaman, ogrenci_adi, metin_konusu, soru, cevap])

# ==========================================
# 4. YAN MENÜ (ÖĞRETMEN PANELİ)
# ==========================================
with st.sidebar:
    st.header("🎓 Araştırmacı Paneli")
    st.info("Sadeleştirilmiş metni dosya olarak yükleyin.")
    
    metin_konusu = st.text_input("Metnin Konusu:", value="Genel Okuma")
    
    # --- YENİ DOSYA YÜKLEME ALANI ---
    yuklenen_dosya = st.file_uploader("Dosya Yükle (PDF, Word veya TXT)", type=["txt", "pdf", "docx"])
    
    if yuklenen_dosya is not None:
        # Dosya yüklendiyse içini oku
        okuma_metni = metin_oku(yuklenen_dosya)
        st.success(f"✅ {yuklenen_dosya.name} başarıyla yüklendi!")
    else:
        # Yüklenmediyse varsayılanı kullan
        varsayilan = "Lütfen sol menüden bir dosya yükleyin..."
        okuma_metni = varsayilan
        st.warning("Henüz dosya yüklenmedi.")

    st.divider()
    st.caption("Veriler 'tez_verileri.csv' dosyasına kaydediliyor.")

# ==========================================
# 5. ANA EKRAN (ÖĞRENCİ ARAYÜZÜ)
# ==========================================
st.title("🌟 Okuma Dostum")

if "ogrenci_adi" not in st.session_state:
    st.session_state["ogrenci_adi"] = ""

if st.session_state["ogrenci_adi"] == "":
    st.info("👋 Merhaba! Başlamadan önce ismini yazar mısın?")
    isim = st.text_input("Adın Soyadın:")
    if st.button("Başla"):
        if isim:
            st.session_state["ogrenci_adi"] = isim
            st.rerun()
else:
    st.success(f"Hoş geldin, {st.session_state['ogrenci_adi']}! 🚀")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📖 Okuma Parçası")
        # Metni kutu içinde gösterelim
        st.text_area("Metin İçeriği", value=okuma_metni, height=400, disabled=True)

    with col2:
        st.subheader("💬 Sohbet Arkadaşın")

        if "messages" not in st.session_state:
            st.session_state["messages"] = [{"role": "assistant", "content": "Metinle ilgili aklına takılan ne varsa sorabilirsin! 👋"}]

        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        if soru := st.chat_input("Sorunu buraya yaz..."):
            st.session_state.messages.append({"role": "user", "content": soru})
            st.chat_message("user").write(soru)

            # --- GÜNCEL PROMPT (ÇOCUK DOSTU) ---
            system_prompt = f"""
            Sen öğrenme güçlüğü yaşayan ortaokul öğrencileri için neşeli, sabırlı bir 'Okuma Arkadaşısın'.
            Öğrenci: {st.session_state['ogrenci_adi']}
            Metin: {okuma_metni}

            KURALLAR:
            1. Çok basit, kısa cümleler kur (10 yaş seviyesi).
            2. Zor kavramları günlük hayattan benzetmelerle anlat.
            3. Asla sadece cevabı verme, ipucu vererek yönlendir.
            4. Bol emoji kullan (🌟, 👍, 🧠).
            5. Motive edici ol.
            """

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": soru}
                    ]
                )
                cevap = response.choices[0].message.content
                
                st.session_state.messages.append({"role": "assistant", "content": cevap})
                st.chat_message("assistant").write(cevap)
                
                # Veriyi kaydet
                veriyi_kaydet(st.session_state['ogrenci_adi'], metin_konusu, soru, cevap)
                
            except Exception as e:

                st.error("Bir hata oluştu. Lütfen öğretmeninize haber verin.")
                import os

st.sidebar.write("---")

if os.path.exists("tez_verileri.csv"): 
    with open("tez_verileri.csv", "rb") as f: 
                st.sidebar.download_button("Verileri İndir", f, "tez_verileri.csv")
