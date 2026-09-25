"""Output screenshots: image files the student saves in the zip's
`output_screenshots` folder. They are NOT part of the .docx report.

Which images exist, and whether each one is a real, readable image, is a fact
decided here by code -- not by an LLM's read of the file list -- so the same zip
always gets the same "you are missing screenshots" verdict. The OCR text of the
images is only supporting evidence handed to the reviewers.

The archive is only ever read in memory, never extracted to disk.
"""
from __future__ import annotations

import io
import re
from pathlib import PurePosixPath
from typing import Any

from PIL import Image

from app import config
from app.ocr.extractor import _ocr_one, summarize_for_llm

# OCR is the slow part, so only the first few images are read; every image is
# still COUNTED. A single screenshot larger than this is refused outright.
MAX_OCR_IMAGES = 12
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def is_screenshot_path(path: str) -> bool:
    """An image sitting in a folder whose name mentions "screenshot"
    (output_screenshots/, screenshots/, ...)."""
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or PurePosixPath(parts[-1]).suffix.lower() not in config.IMAGE_EXTENSIONS:
        return False
    return any("screenshot" in part.lower() for part in parts[:-1])


def _is_real_image(raw: bytes) -> bool:
    try:
        Image.open(io.BytesIO(raw)).verify()
    except Exception:  # not an image, truncated, or a decompression-bomb guard tripped
        return False
    return True


def ingest_screenshots(archive: Any, infos: list[Any]) -> dict[str, Any]:
    """Find, validate and OCR the screenshots in an already-opened zip.

    Returns files (every screenshot-looking image), valid_files (the ones that
    are real readable images -- only these count), and ocr_text for the reviewers.
    """
    files: list[str] = []
    valid: list[str] = []
    ocr_items = []
    for info in infos:
        if info.is_dir() or not is_screenshot_path(info.filename):
            continue
        files.append(info.filename)
        if info.file_size == 0 or info.file_size > MAX_IMAGE_BYTES:
            continue
        raw = archive.read(info)
        if not _is_real_image(raw):
            continue
        valid.append(info.filename)
        if len(ocr_items) < MAX_OCR_IMAGES:
            ocr_items.append(_ocr_one(info.filename, raw))
    return {
        "files": sorted(files),
        "valid_files": sorted(valid),
        "ocr_text": summarize_for_llm(ocr_items) if ocr_items else "No screenshot images were found in the zip.",
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _stem(filename: str) -> str:
    return _slug(PurePosixPath(filename.replace("\\", "/")).stem)


def normalise_required_screenshots(items: Any) -> list[dict[str, str]]:
    """The guide's screenshot list, cleaned: every entry has a description and a
    safe, numbered .png filename the student can be told to use verbatim."""
    cleaned: list[dict[str, str]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("description", "")).strip():
            continue
        description = str(item["description"]).strip()
        raw_name = str(item.get("filename", "")).strip().replace("\\", "/").rsplit("/", 1)[-1]
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip("-.")
        if not name:
            name = f"{len(cleaned) + 1:02d}-{_slug(str(item.get('module') or description))[:40] or 'screenshot'}"
        if PurePosixPath(name).suffix.lower() not in config.IMAGE_EXTENSIONS:
            name += ".png"
        cleaned.append({
            "filename": name,
            "module": str(item.get("module", "")).strip(),
            "description": description,
            "how_to_capture": str(item.get("how_to_capture", "")).strip(),
            "linked_requirement": str(item.get("linked_requirement", "")).strip(),
        })
    return cleaned


def ensure_screenshot_folder(guide: dict[str, Any]) -> dict[str, Any]:
    """If screenshots are required, `<root>/output_screenshots` must be a
    required folder and appear in the folder tree the student is shown --
    whatever the model happened to write."""
    if not guide.get("required_screenshots"):
        return guide
    paths = list(guide.get("required_paths") or [])
    tree = list(guide.get("folder_structure") or [])
    if not any("screenshot" in str(item.get("path", "")).lower() for item in paths):
        first = str(paths[0].get("path", "")) if paths else (tree[0] if tree else "")
        root = first.replace("\\", "/").strip("/").split("/", 1)[0] or "project"
        paths.append({
            "path": f"{root}/output_screenshots", "type": "dir",
            "description": "Screenshots of your running project - one image file for each item under Required Screenshots.",
        })
    if not any("screenshot" in str(line).lower() for line in tree):
        first_path = str(paths[-1].get("path", ""))
        tree.append(f"{first_path}/")
    guide["required_paths"] = paths
    guide["folder_structure"] = tree
    return guide


def screenshot_status(guide: dict[str, Any], evidence: dict[str, Any] | None) -> dict[str, Any]:
    """How the submitted screenshots compare with what the project needs.

    One valid image is needed per required screenshot. Which file is which is
    only known when the student used the suggested file names, so `matched` /
    `unmatched` are by-name hints; `shortfall` is the count that decides.
    """
    required = normalise_required_screenshots(guide.get("required_screenshots"))
    evidence = evidence or {}
    valid = list(evidence.get("valid_files") or [])
    unreadable = [name for name in evidence.get("files") or [] if name not in valid]
    stems = {_stem(name) for name in valid}
    matched = [item for item in required if _stem(item["filename"]) in stems]
    unmatched = [item for item in required if _stem(item["filename"]) not in stems]
    shortfall = max(len(required) - len(valid), 0)
    return {
        "required": required, "found_files": valid, "unreadable_files": unreadable,
        "matched": matched, "unmatched": unmatched,
        "shortfall": shortfall, "complete": shortfall == 0,
    }
