def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Paragraph-aware fixed-size chunking: pack consecutive paragraphs up to
    `chunk_size`, hard-slicing (with overlap) only when a single paragraph exceeds it.
    No tokenizer/semantic splitting — sized for a personal-notes RAG store, not a
    production search engine."""

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_slice(paragraph, chunk_size, overlap))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)
    return chunks


def _hard_slice(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    return [text[start : start + chunk_size] for start in range(0, len(text), step)]
