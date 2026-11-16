from __future__ import annotations

import io
import os

import pytesseract
from PIL import Image, UnidentifiedImageError

if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

_OCR_LANGUAGES = "por+eng"
# Capturas de tela de bilhete tem de 300 a 600 px de largura, e a letra fica pequena demais para o
# Tesseract (perde o ponto decimal, le "R$" como "RS"). Abaixo desta largura, a imagem e ampliada 2x;
# fotos de camera, ja grandes, passam sem mudanca (feat-017).
_UPSCALE_BELOW_WIDTH = 1200
_UPSCALE_FACTOR = 2


def upscale_for_ocr(image: Image.Image) -> Image.Image:
    if image.width >= _UPSCALE_BELOW_WIDTH:
        return image
    size = (image.width * _UPSCALE_FACTOR, image.height * _UPSCALE_FACTOR)
    return image.resize(size, Image.Resampling.LANCZOS)


def extract_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError:
        return ""
    return str(pytesseract.image_to_string(upscale_for_ocr(image), lang=_OCR_LANGUAGES))
