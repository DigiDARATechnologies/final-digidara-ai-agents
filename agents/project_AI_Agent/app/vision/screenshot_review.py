"""AI review of the output screenshots in a submitted zip.

A vision model looks at every candidate image (see
app/ingestion/screenshots.py:ingest_screenshots), says what each one shows,
whether it is a screenshot of the running project at all (a logo or a stock
photo is not), and which of the project's required screenshots it proves.
The student is then told exactly which screenshot is still missing, whatever
the images were called and wherever in the zip they were saved.

Never fatal: if the model or the zip cannot be read, the caller falls back to
counting screenshot images (see screenshot_status).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import zipfile
from typing import Any

from PIL import Image

from app.ingestion.screenshots import normalise_required_screenshots
from app.llm.client import call_json

logger = logging.getLogger("capstone.screenshot_review")

# One vision call holds at most this many images; marked screenshots go first.
MAX_REVIEW_IMAGES = 16
_MAX_SIDE = 768
_OCR_CHARS_PER_IMAGE = 400


def _data_url(raw: bytes) -> str:
    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGB")
        image.thumbnail((_MAX_SIDE, _MAX_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _ocr_by_file(ocr_text: str) -> dict[str, str]:
    """Split summarize_for_llm's "[Screenshot N: path]\\ntext" blocks per file."""
    found: dict[str, str] = {}
    for match in re.finditer(r"\[Screenshot \d+: (.+?)\](.*?)(?=\n\n\[Screenshot \d+: |\Z)", ocr_text or "", re.DOTALL):
        found[match.group(1).strip()] = " ".join(match.group(2).split())[:_OCR_CHARS_PER_IMAGE]
    return found


def _prompt(project_title: str, required: list[dict[str, str]], files: list[str], ocr: dict[str, str]) -> str:
    wanted = "\n".join(
        f'  - "{item["filename"]}" [{item["module"] or "screenshot"}]: {item["description"]}'
        for item in required
    )
    images = "\n".join(
        f'  Image {index}: {path}' + (f'\n    Text read from it: {ocr[path]}' if ocr.get(path) else "")
        for index, path in enumerate(files, start=1)
    )
    return f"""You check the output screenshots a student submitted for a capstone project.
Project: {project_title or "(untitled)"}

The project needs these screenshots:
{wanted}

The student's zip holds these images, attached in this order:
{images}

For every image, decide:
- "shows": one short sentence on what is visible (which page, form, chart, terminal output, error, ...).
- "is_app_screenshot": true when it is a screenshot of THIS project running (a browser page,
  app window, terminal or test output). False for logos, icons, illustrations, stock photos,
  diagrams, photos of paper, or a screenshot of something unrelated (a file explorer, a code editor
  with no running output, another website).

For every required screenshot, decide whether any image shows it:
- "present" when an app screenshot clearly shows that page, feature or output. Judge by what is
  visible, never by the file name. Be fair: it counts if the feature is visible even when the
  exact sample data or styling differs. One image may prove more than one required screenshot.
- "missing" when no image shows it. In "reason", say what is missing in one short sentence a
  student understands (for example "No image shows a login page with username and password fields.").

Reply with ONLY this JSON:
{{"images": [{{"image": 1, "shows": "...", "is_app_screenshot": true}}],
  "required": [{{"filename": "<exact required file name>", "status": "present" | "missing", "image": <image number or null>, "reason": "..."}}]}}"""


def _normalise(raw: dict[str, Any], files: list[str], required: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("images"), list) or not isinstance(raw.get("required"), list):
        raise ValueError("the screenshot review reply has no images/required lists")
    images = []
    by_index: dict[int, dict[str, Any]] = {}
    for entry in raw.get("images") or []:
        try:
            index = int(entry.get("image"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= index <= len(files) and index not in by_index:
            by_index[index] = {
                "file": files[index - 1],
                "shows": str(entry.get("shows") or "").strip(),
                "is_app_screenshot": entry.get("is_app_screenshot") is True,
            }
    for index in range(1, len(files) + 1):
        # An image the model skipped is not silently counted as a screenshot.
        images.append(by_index.get(index) or {"file": files[index - 1], "shows": "", "is_app_screenshot": False})

    names = {item["filename"] for item in required}
    verdicts = []
    seen: set[str] = set()
    for entry in raw.get("required") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("filename") or "").strip()
        if name not in names or name in seen:
            continue
        seen.add(name)
        status = str(entry.get("status") or "").strip().lower()
        file = None
        try:
            index = int(entry.get("image"))
            if 1 <= index <= len(files):
                file = files[index - 1]
        except (TypeError, ValueError):
            pass
        present = status == "present" and file is not None and images[files.index(file)]["is_app_screenshot"]
        verdicts.append({
            "filename": name,
            "status": "present" if present else "missing",
            "file": file if present else None,
            "reason": str(entry.get("reason") or "").strip(),
        })
    for item in required:
        if item["filename"] not in seen:
            verdicts.append({"filename": item["filename"], "status": "missing", "file": None, "reason": ""})
    return {"ok": True, "images": images, "required": verdicts}


def review_screenshots(
    zip_path: str, guide: dict[str, Any], evidence: dict[str, Any], project_title: str = "", llm: Any = call_json,
) -> dict[str, Any] | None:
    """None when there is nothing to review; {"ok": False, ...} when the
    review could not run; otherwise {"ok": True, "images": [...], "required": [...]}."""
    required = normalise_required_screenshots(guide.get("required_screenshots"))
    files = list(evidence.get("valid_files") or []) + list(evidence.get("other_images") or [])
    if not required or not files:
        return None
    files = files[:MAX_REVIEW_IMAGES]
    try:
        with zipfile.ZipFile(zip_path) as archive:
            urls = [_data_url(archive.read(name)) for name in files]
        raw = llm(
            system=_prompt(project_title, required, files, _ocr_by_file(evidence.get("ocr_text", ""))),
            user="Look at the attached images and answer now.",
            image_data_url=urls,
            temperature=0,
        )
        review = _normalise(raw, files, required)
    except Exception as exc:  # the zip, the image or the model failed: fall back to counting
        logger.warning("screenshot review failed for %s: %s", zip_path, exc)
        return {"ok": False, "error": str(exc)[:300]}
    logger.info("screenshot review: %s", json.dumps([v["status"] for v in review["required"]]))
    return review
