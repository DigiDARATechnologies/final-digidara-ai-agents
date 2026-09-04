"""DocxIngestNode (deterministic, non-LLM) — parses the submitted .docx into
section headings + body text + screenshot OCR text."""
from __future__ import annotations

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from app.ocr.extractor import extract_images_from_docx, summarize_for_llm


class DocxIngestError(Exception):
    pass


def ingest_docx(docx_path: str) -> dict:
    try:
        document = Document(docx_path)
    except PackageNotFoundError as exc:
        raise DocxIngestError("The uploaded file is not a valid .docx package.") from exc
    except Exception as exc:
        raise DocxIngestError(f"Could not open the .docx file: {exc}") from exc

    sections: dict[str, str] = {}
    current_heading = "Preamble"
    sections[current_heading] = ""

    for para in document.paragraphs:
        # para.style can legitimately be None (e.g. direct-formatted or
        # list paragraphs in real-world Word/Google-Docs exports) — synthetic
        # test docs built with python-docx always set a style, which is why
        # this only surfaces on real user-submitted files.
        style = para.style
        style_name = (style.name or "").lower() if style is not None else ""
        text = para.text.strip()
        if style_name.startswith("heading") or style_name in ("title",):
            if text:
                current_heading = text
                sections.setdefault(current_heading, "")
            continue
        if text:
            sections[current_heading] = (sections.get(current_heading, "") + "\n" + text).strip()

    # Drop an empty preamble bucket — it adds noise with no signal.
    if not sections.get("Preamble"):
        sections.pop("Preamble", None)

    images = extract_images_from_docx(docx_path)
    screenshot_text = summarize_for_llm(images)

    return {
        "sections": sections,
        "screenshots_present": len(images) > 0,
        "screenshot_count": len(images),
        "screenshot_ocr_text": screenshot_text,
    }
