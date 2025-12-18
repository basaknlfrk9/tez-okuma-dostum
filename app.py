with st.chat_message("assistant"):
    ek_bilgi = f"PDF İçeriği:\n{icerik[:1500]}\n\n" if icerik else ""

    yanit = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bir okuma asistanısın."},
            {"role": "user", "content": ek_bilgi + soru}
        ]
    )

    cevap = yanit.choices[0].message.content
    st.write(cevap)

st.session_state.messages.append({
    "role": "assistant",
    "content": cevap
})

# ---- GEÇMİŞİ KAYDET (BURASI AYRI VE DIŞARIDA) ----
with open(dosya_adi, "w", encoding="utf-8") as f:
    json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
