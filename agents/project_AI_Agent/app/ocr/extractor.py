"""
OCR-based screenshot validation.

Per product decision: submitted output screenshots are validated by extracting
their text via OCR (Tesseract) rather than sending raw images to a
vision-capable LLM. This keeps the LLM layer provider-agnostic (works with
text-only models too — Groq's fast text models, local Ollama, etc.) and gives
the validator nodes something deterministic and checkable to read.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from PIL import Image

from app import config

try:
    import pytesseract

    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False


@dataclass
class ExtractedImage:
    filename: str
    ocr_text: str
    ocr_error: str | None = None


def extract_images_from_docx(docx_path: str) -> list[ExtractedImage]:
    """Docx files are zip archives; embedded images live under word/media/."""
    results: list[ExtractedImage] = []
    with zipfile.ZipFile(docx_path) as zf:
        media_files = sorted(
            name for name in zf.namelist()
            if name.startswith("word/media/")
            and ("." + name.rsplit(".", 1)[-1]).lower() in config.IMAGE_EXTENSIONS
        )
        for name in media_files:
            raw = zf.read(name)
            results.append(_ocr_one(name, raw))
    return results


def _ocr_one(filename: str, raw_bytes: bytes) -> ExtractedImage:
    if not _TESSERACT_AVAILABLE:
        return ExtractedImage(
            filename=filename,
            ocr_text="",
            ocr_error=(
                "pytesseract/Tesseract binary not installed on this server — "
                "screenshot presence is confirmed but text could not be extracted."
            ),
        )
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        text = pytesseract.image_to_string(image)
        return ExtractedImage(filename=filename, ocr_text=text.strip())
    except Exception as exc:  # corrupt image, unsupported format, etc.
        return ExtractedImage(filename=filename, ocr_text="", ocr_error=str(exc))


def summarize_for_llm(images: list[ExtractedImage]) -> str:
    """Render extracted screenshot OCR text into a compact block the output
    verification prompt can reason over."""
    if not images:
        return "No embedded images/screenshots were found in the document."
    parts = []
    for i, img in enumerate(images, start=1):
        if img.ocr_error and not img.ocr_text:
            parts.append(f"[Screenshot {i}: {img.filename}] (OCR failed: {img.ocr_error})")
        else:
            text = img.ocr_text or "(no text detected in image)"
            parts.append(f"[Screenshot {i}: {img.filename}]\n{text}")
    return "\n\n".join(parts)
