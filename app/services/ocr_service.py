import io

import pytesseract
from PIL import Image


class OcrError(Exception):
    """Raised when OCR cannot be performed."""


def ocr_page(page) -> str:
    """Render a PyMuPDF page to an image and run Tesseract on it."""
    pixmap = page.get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrError("OCR engine (Tesseract) is not installed on the server.") from exc
    except pytesseract.TesseractError as exc:
        raise OcrError("OCR failed while reading a page of the PDF.") from exc
