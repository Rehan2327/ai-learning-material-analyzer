import re
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.services import ocr_service

MIN_CHARS_PER_PAGE = 25  # fewer characters than this = page has no useful text


class PdfProcessingError(Exception):
    """The PDF is corrupted, encrypted or contains no readable text."""


@dataclass
class ExtractionResult:
    text: str
    used_ocr: bool


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(path: str, max_ocr_pages: int) -> ExtractionResult:
    """Extract embedded text; OCR only the pages that have no useful text."""
    try:
        doc = fitz.open(path)
    except Exception as exc:  # PyMuPDF raises several exception types
        raise PdfProcessingError("The PDF is corrupted or cannot be opened.") from exc

    with doc:
        if doc.needs_pass:
            raise PdfProcessingError("Password-protected PDFs are not supported.")
        if doc.page_count == 0:
            raise PdfProcessingError("The PDF has no pages.")

        pages: list[str] = []
        ocr_pages = 0
        for page in doc:
            page_text = page.get_text().strip()
            if len(page_text) < MIN_CHARS_PER_PAGE and ocr_pages < max_ocr_pages:
                page_text = ocr_service.ocr_page(page).strip()
                ocr_pages += 1
            pages.append(page_text)

    text = clean_text("\n\n".join(pages))
    if not text:
        raise PdfProcessingError("No readable text could be found in this PDF.")
    return ExtractionResult(text=text, used_ocr=ocr_pages > 0)
