"""OCR text extraction for a bet-slip screenshot. Best-effort: no bookmaker-specific
template, no real bet-slip sample was available to validate against during
development (see docs/DECISIONS-LOG.md 2026-09-08) - garbled or partial text is
expected, not an error. Whatever `extraction.py` can't confidently pull out of the
result falls back to asking the user directly.
"""

from __future__ import annotations

import io
import os

import pytesseract
from PIL import Image, UnidentifiedImageError

if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

_OCR_LANGUAGES = "por+eng"


def extract_text(image_bytes: bytes) -> str:
    """Returns the raw OCR text, or "" if the bytes aren't a readable image -
    never raises, matching the "never crash on a malformed image" requirement.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError:
        return ""
    return str(pytesseract.image_to_string(image, lang=_OCR_LANGUAGES))
