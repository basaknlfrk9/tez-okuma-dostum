def split_paragraphs(text: str):
    """
    ÖÖG için güvenli bölümlendirme:
    1) Boş satırlarla ayrılmış paragraf varsa onu koru.
    2) Yoksa cümlelere ayır.
    3) Cümleleri hedef uzunlukta (220-320 char) bloklara birleştir.
    4) Cümle ortasında asla bölme (çok uzun tek cümle hariç).
    """
    text = (text or "").replace("\r", "\n").strip()
    if not text:
        return []

    # 1) Gerçek paragraf var mı? (en az 2 paragraf)
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(raw_paras) >= 2:
        # Paragrafları gerekirse cümle bloklarına bölelim (çok uzun paragraf olursa)
        return _chunk_by_sentences(raw_paras)

    # 2) Paragraf yoksa: cümlelere ayırıp blokla
    return _chunk_by_sentences([text])


def _split_sentences_tr(s: str):
    """
    Basit TR cümle ayırıcı. Nokta/ünlem/soru işaretinden sonra boşluk ve büyük harf geliyorsa ayırır.
    Kısaltmalar %100 çözülmez ama ÖÖG için yeterince stabil.
    """
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return []
    # Cümle sonları: . ! ? … (veya üç nokta)
    parts = re.split(r"(?<=[.!?…])\s+", s)
    return [p.strip() for p in parts if p.strip()]


def _force_split_long_sentence(sent: str, max_len=320):
    """
    Çok uzun tek cümleyi cümle ortasında kesmeden bölmeye çalışır:
    önce virgül; yoksa 've/ama/fakat/çünkü' gibi bağlaçlar; en son boşluk.
    """
    sent = (sent or "").strip()
    if len(sent) <= max_len:
        return [sent]

    # önce virgül
    if "," in sent:
        pieces = []
        buf = ""
        for part in sent.split(","):
            part = part.strip()
            candidate = (buf + (", " if buf else "") + part).strip()
            if len(candidate) <= max_len:
                buf = candidate
            else:
                if buf:
                    pieces.append(buf)
                buf = part
        if buf:
            pieces.append(buf)
        return pieces

    # bağlaç dene
    for conj in [" çünkü ", " ama ", " fakat ", " ancak ", " ve ", " sonra ", " böylece "]:
        if conj in sent:
            chunks = []
            buf = ""
            parts = sent.split(conj)
            for i, part in enumerate(parts):
                part = part.strip()
                glue = conj.strip() if i > 0 else ""
                candidate = (buf + (" " + glue + " " if buf and glue else "") + part).strip()
                if len(candidate) <= max_len:
                    buf = candidate
                else:
                    if buf:
                        chunks.append(buf)
                    buf = (glue + " " + part).strip() if glue else part
            if buf:
                chunks.append(buf)
            # hâlâ çok uzunsa en sona bırakırız
            final = []
            for c in chunks:
                if len(c) > max_len:
                    final.extend(_force_split_long_sentence(c, max_len=max_len))
                else:
                    final.append(c)
            return final

    # en son çare: kelime bazlı
    words = sent.split()
    chunks, buf = [], ""
    for w in words:
        candidate = (buf + " " + w).strip()
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            buf = w
    if buf:
        chunks.append(buf)
    return chunks


def _chunk_by_sentences(paragraph_list, target_min=220, target_max=320):
    """
    Paragrafları cümle bloklarına çevirir.
    - target_max üstünü geçmemeye çalışır.
    - bloklar cümle bazında birleştirilir.
    """
    out = []
    for para in paragraph_list:
        sentences = _split_sentences_tr(para)

        # çok kısa/boş olmasın
        if not sentences:
            continue

        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue

            # aşırı uzun tek cümle: güvenli böl
            if len(s) > target_max:
                long_parts = _force_split_long_sentence(s, max_len=target_max)
                for lp in long_parts:
                    if not buf:
                        buf = lp
                    else:
                        candidate = (buf + " " + lp).strip()
                        if len(candidate) <= target_max:
                            buf = candidate
                        else:
                            out.append(buf)
                            buf = lp
                continue

            # normal cümle: bloğa ekle
            if not buf:
                buf = s
            else:
                candidate = (buf + " " + s).strip()
                if len(candidate) <= target_max:
                    buf = candidate
                else:
                    out.append(buf)
                    buf = s

        if buf:
            out.append(buf)

        # paragraflar arasında minik görsel boşluk etkisi için (isteğe bağlı)
        # out.append("")  # istemiyorsan kapalı kalsın

    # Çok küçük blokları komşusuyla birleştir (ÖÖG için tek kelimelik bloklar olmasın)
    merged = []
    for block in out:
        block = block.strip()
        if not block:
            continue
        if merged and len(block) < 80 and len(merged[-1]) + 1 + len(block) <= target_max:
            merged[-1] = (merged[-1] + " " + block).strip()
        else:
            merged.append(block)

    return merged
