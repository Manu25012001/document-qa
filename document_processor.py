"""PDF text extraction and page-aware, overlapping text chunking."""
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: int
    page_start: int
    page_end: int
    text: str

    def as_dict(self):
        return {"chunk_id": self.chunk_id, "page_start": self.page_start,
                "page_end": self.page_end, "text": self.text}


def extract_pages(pdf_bytes: bytes, max_pages: int = 500) -> list[tuple[int, str]]:
    import pymupdf

    if not pdf_bytes:
        raise ValueError("The uploaded PDF is empty.")
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            if doc.is_encrypted:
                raise ValueError("This PDF is password-protected. Please upload an unlocked PDF.")
            if len(doc) == 0:
                raise ValueError("The PDF contains no pages.")
            if len(doc) > max_pages:
                raise ValueError(f"This PDF has more than the {max_pages}-page processing limit.")
            pages = [(number, page.get_text("text").strip())
                     for number, page in enumerate(doc, start=1)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The file could not be read as a valid PDF.") from exc
    if not any(text for _, text in pages):
        raise ValueError("No selectable text was found. Scanned PDFs need OCR before upload.")
    return pages


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int = 1200,
                overlap: int = 150) -> list[Chunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than chunk size.")
    chunks = []
    for page_number, page_text in pages:
        text = " ".join(page_text.split())
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            content = text[start:end].strip()
            if content:
                chunks.append(Chunk(len(chunks) + 1, page_number, page_number, content))
            if end == len(text):
                break
            start = end - overlap
    return chunks
