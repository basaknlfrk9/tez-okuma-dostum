import streamlit as st
import time

# =========================================
# STATE BAŞLAT
# =========================================
def init_state():
    defaults = {
        "phase": "start",
        "q_idx": 0,
        "correct_map": {},
        "question_status": {},
        "skipped_questions": [],
        "hints": 0,
        "start_t": time.time(),
        "prediction": "",
        "summary": "",
        "story_map": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================================
# VERİ
# =========================================
metin = """
Ali sabah erkenden kalktı. Okula gitmek için hazırlanıyordu.

Yolda giderken küçük bir kedi gördü. Kedi çok aç görünüyordu.

Ali evine geri dönüp süt getirdi ve kediyi besledi.

Daha sonra okula geç kaldı ama mutlu hissediyordu.
"""

paragraflar = [p.strip() for p in metin.split("\n") if p.strip()]

sorular = [
    {"soru": "Ali sabah ne yaptı?", "A": "Uyudu", "B": "Hazırlandı", "C": "Oyun oynadı", "dogru": "B"},
    {"soru": "Ali ne gördü?", "A": "Kedi", "B": "Kuş", "C": "Köpek", "dogru": "A"},
    {"soru": "Ali neden mutlu oldu?", "A": "Geç kaldı", "B": "Kediyi besledi", "C": "Uyudu", "dogru": "B"},
]

# =========================================
# YARDIMCI
# =========================================
def go(phase):
    st.session_state.phase = phase
    st.rerun()

# =========================================
# 1) BAŞLANGIÇ
# =========================================
if st.session_state.phase == "start":
    st.title("📘 Okuma Uygulaması")

    if st.button("Başla"):
        go("read")

# =========================================
# 2) OKUMA
# =========================================
elif st.session_state.phase == "read":
    st.subheader("📖 Metni Oku")

    for p in paragraflar:
        st.write(p)

    if st.button("Devam Et"):
        go("pre")

# =========================================
# 3) OKUMA ÖNCESİ
# =========================================
elif st.session_state.phase == "pre":
    st.subheader("🧠 Tahmin Yap")

    st.session_state.prediction = st.text_input("Metin ne hakkında olabilir?")

    if st.button("Devam"):
        go("story")

# =========================================
# 4) ÖYKÜ HARİTASI
# =========================================
elif st.session_state.phase == "story":
    st.subheader("🧩 Öykü Haritası")

    karakter = st.text_input("Karakter")
    mekan = st.text_input("Mekan")
    olay = st.text_input("Olay")
    sonuc = st.text_input("Sonuç")

    if st.button("Kaydet"):
        st.session_state.story_map = {
            "karakter": karakter,
            "mekan": mekan,
            "olay": olay,
            "sonuc": sonuc,
        }
        go("questions")

# =========================================
# 5) SORULAR
# =========================================
elif st.session_state.phase == "questions":
    i = st.session_state.q_idx
    soru = sorular[i]

    st.markdown(f"### Soru {i+1}")
    st.write(soru["soru"])

    secim = st.radio(
        "Seç",
        ["A", "B", "C"],
        format_func=lambda x: f"{x}) {soru[x]}"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cevapla"):
            if secim == soru["dogru"]:
                st.success("✅ Doğru")
                st.session_state.correct_map[i] = 1
            else:
                st.error("❌ Yanlış")
                st.session_state.correct_map[i] = 0

            st.session_state.question_status[i] = "done"

            if i < len(sorular) - 1:
                st.session_state.q_idx += 1
                st.rerun()
            else:
                go("finish")

    with col2:
        if st.button("💡 İpucu"):
            st.info("Metni tekrar düşün")
            st.session_state.hints += 1

    if st.button("⏭️ Geç"):
        st.session_state.skipped_questions.append(i)
        st.session_state.question_status[i] = "skipped"

        if i < len(sorular) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            go("finish")

# =========================================
# 6) BİTİŞ
# =========================================
elif st.session_state.phase == "finish":
    st.subheader("🎉 Sonuç")

    total = len(sorular)
    dogru = sum(st.session_state.correct_map.values())
    yanlis = total - dogru - len(st.session_state.skipped_questions)
    gecilen = len(st.session_state.skipped_questions)

    sure = round((time.time() - st.session_state.start_t)/60, 2)
    basari = int((dogru / total) * 100)

    st.write(f"Doğru: {dogru}")
    st.write(f"Yanlış: {yanlis}")
    st.write(f"Geçilen: {gecilen}")
    st.write(f"Süre: {sure} dk")
    st.write(f"Başarı: %{basari}")

    # ROZET
    if basari >= 80:
        st.success("🏆 Harika!")
    elif basari >= 50:
        st.info("👍 İyi!")
    else:
        st.warning("💪 Gelişebilirsin")

    # RAPOR
    rapor = f"""
OKUMA RAPORU

Doğru: {dogru}
Yanlış: {yanlis}
Geçilen: {gecilen}
Başarı: %{basari}
Süre: {sure} dk

Tahmin: {st.session_state.prediction}

Öykü Haritası:
Karakter: {st.session_state.story_map.get('karakter')}
Mekan: {st.session_state.story_map.get('mekan')}
Olay: {st.session_state.story_map.get('olay')}
Sonuç: {st.session_state.story_map.get('sonuc')}
"""

    st.download_button("📥 Rapor İndir", rapor, file_name="rapor.txt")

    if st.button("🔄 Yeniden Başla"):
        st.session_state.clear()
        st.rerun()
