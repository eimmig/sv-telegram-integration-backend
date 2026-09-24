from __future__ import annotations

import io
import os

import pytesseract
from PIL import Image, UnidentifiedImageError

if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

_OCR_LANGUAGES = "por+eng"


def extract_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError:
        return ""
    return str(pytesseract.image_to_string(image, lang=_OCR_LANGUAGES))
