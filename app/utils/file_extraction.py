import io

from pypdf import PdfReader

from app.core.exceptions import ValidationFailedError


def extract_text_from_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValidationFailedError("Could not parse PDF file") from exc

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise ValidationFailedError("No extractable text found in PDF")
    return text


def extract_text_from_txt(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValidationFailedError("Could not decode text file") from exc

    if not text.strip():
        raise ValidationFailedError("Text file is empty")
    return text
