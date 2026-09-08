import io

from PIL import Image, ImageDraw, ImageFont

from telegram_integration.ocr import extract_text


def _render_text_image(text: str) -> bytes:
    image = Image.new("RGB", (600, 100), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    draw.text((10, 10), text, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_text_reads_a_synthetic_rendered_image() -> None:
    image_bytes = _render_text_image("ODD 1.85")

    text = extract_text(image_bytes)

    assert "1.85" in text or "1,85" in text


def test_extract_text_returns_empty_string_for_non_image_bytes() -> None:
    assert extract_text(b"not an image, just random bytes") == ""
