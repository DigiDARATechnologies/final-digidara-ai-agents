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


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path.replace("\\", "/")).parts


def _is_image(path: str) -> bool:
    parts = _parts(path)
    return bool(parts) and PurePosixPath(parts[-1]).suffix.lower() in config.IMAGE_EXTENSIONS


# Folder or file names that say "this is a screenshot of the output".
_SCREENSHOT_HINT_RE = re.compile(r"screen[\s_-]?shot|capture|snap|output|result", re.IGNORECASE)
# Numbered images ("01-login.png", "2_dashboard.jpg") are how the guide names them.
_NUMBERED_RE = re.compile(r"^\d{1,3}[\s._-]")
# Images that are part of the app itself, not pictures of it running.
_ASSET_DIRS = {
    "public", "assets", "asset", "static", "img", "imgs", "image", "images", "icons", "icon", "media",
    "fonts", "res", "resources", "drawable", "mipmap", "src", "templates", "components",
}
_ASSET_NAME_RE = re.compile(
    r"favicon|logo|icon|sprite|hero|banner|background|^bg[\s._-]|avatar|placeholder|apple-touch|android-chrome|mstile",
    re.IGNORECASE,
)
# An "image" smaller than this on either side is an icon, not a screenshot.
_MIN_SCREENSHOT_SIDE = 120


def is_screenshot_path(path: str) -> bool:
    """An image sitting in a folder whose name mentions "screenshot"
    (output_screenshots/, screenshots/, ...)."""
    if not _is_image(path):
        return False
    return any("screenshot" in part.lower() for part in _parts(path)[:-1])


def looks_like_screenshot(path: str) -> bool:
    """An image whose folder or file name says it is a screenshot of the
    output, wherever it sits in the zip (output_screenshots/, Screenshots/,
    outputs/, "Screenshot 2026-10-22.png", "01-login.png", ...)."""
    if not _is_image(path):
        return False
    parts = _parts(path)
    name = parts[-1]
    if any(_SCREENSHOT_HINT_RE.search(part) for part in parts[:-1]):
        return True
    return bool(_SCREENSHOT_HINT_RE.search(name) or _NUMBERED_RE.match(name))


def is_app_asset(path: str) -> bool:
    """A logo, icon, hero image and the like -- part of the app, not a picture of it."""
    parts = _parts(path)
    if not parts or _ASSET_NAME_RE.search(PurePosixPath(parts[-1]).stem):
        return True
    return any(part.lower() in _ASSET_DIRS for part in parts[:-1])


def _image_size(raw: bytes) -> tuple[int, int] | None:
    """(width, height) of a real, readable image; None for anything else."""
    try:
        with Image.open(io.BytesIO(raw)) as image:
            size = image.size
            image.verify()
    except Exception:  # not an image, truncated, or a decompression-bomb guard tripped
        return None
    return size


def _is_real_image(raw: bytes) -> bool:
    return _image_size(raw) is not None


def ingest_screenshots(archive: Any, infos: list[Any]) -> dict[str, Any]:
    """Find, validate and OCR the screenshots in an already-opened zip.

    Screenshots are found by what they are, not by one exact folder name:
    - valid_files: readable images whose folder or file name marks them as
      screenshots (output_screenshots/, screenshots/, "01-login.png", ...).
    - other_images: every other readable, screenshot-sized image that is not
      an obvious app asset (logo, icon, ...). The AI screenshot review looks at
      these too, so a screenshot saved in an oddly named folder still counts.
    - loose_files: the other_images outside asset folders (public/, assets/,
      src/, ...) -- what counts by number when the AI review is not available.
    - files: every image seen, including unreadable ones.
    """
    files: list[str] = []
    valid: list[str] = []
    others: list[str] = []
    ocr_items = []
    ocr_queue: list[tuple[str, bytes]] = []
    for info in infos:
        if info.is_dir() or not _is_image(info.filename):
            continue
        marked = looks_like_screenshot(info.filename)
        if not marked and _ASSET_NAME_RE.search(PurePosixPath(_parts(info.filename)[-1]).stem):
            continue
        files.append(info.filename)
        if info.file_size == 0 or info.file_size > MAX_IMAGE_BYTES:
            continue
        raw = archive.read(info)
        size = _image_size(raw)
        if size is None:
            continue
        if marked:
            valid.append(info.filename)
            ocr_queue.insert(sum(1 for name, _ in ocr_queue if looks_like_screenshot(name)), (info.filename, raw))
        elif min(size) >= _MIN_SCREENSHOT_SIDE:
            others.append(info.filename)
            ocr_queue.append((info.filename, raw))
        else:
            files.remove(info.filename)  # an icon-sized picture, not a screenshot
    for name, raw in ocr_queue[:MAX_OCR_IMAGES]:
        ocr_items.append(_ocr_one(name, raw))
    unreadable = [name for name in files if name not in valid and name not in others]
    return {
        "files": sorted(set(valid) | set(unreadable) | {name for name in others}),
        "valid_files": sorted(valid),
        "other_images": sorted(others),
        "loose_files": sorted(name for name in others if not is_app_asset(name)),
        "unreadable_files": sorted(unreadable),
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
    if "unreadable_files" in evidence:
        unreadable = list(evidence.get("unreadable_files") or [])
    else:
        unreadable = [name for name in evidence.get("files") or [] if name not in valid]

    review = evidence.get("ai_review") or {}
    if required and review.get("ok"):
        return _status_from_review(required, review, unreadable)

    # No AI review (none needed, or the vision call failed): count readable
    # screenshots. Images outside a screenshot-named folder count only when
    # there are no marked screenshots at all.
    if not valid:
        valid = list(evidence.get("loose_files") or [])
    stems = {_stem(name) for name in valid}
    matched = [item for item in required if _stem(item["filename"]) in stems]
    unmatched = [item for item in required if _stem(item["filename"]) not in stems]
    shortfall = max(len(required) - len(valid), 0)
    return {
        "required": required, "found_files": valid, "unreadable_files": unreadable,
        "matched": matched, "unmatched": unmatched,
        "shortfall": shortfall, "complete": shortfall == 0, "ai_reviewed": False,
    }


def _status_from_review(required: list[dict[str, str]], review: dict[str, Any], unreadable: list[str]) -> dict[str, Any]:
    """The AI looked at every image: a required screenshot counts as present
    only when an actual screenshot of the app shows it."""
    images = review.get("images") or []
    screenshots = [image["file"] for image in images if image.get("is_app_screenshot")]
    verdicts = {item["filename"]: item for item in review.get("required") or []}
    matched, unmatched = [], []
    for item in required:
        verdict = verdicts.get(item["filename"]) or {}
        if verdict.get("status") == "present" and verdict.get("file") in screenshots:
            matched.append({**item, "found_in": verdict["file"], "reason": verdict.get("reason", "")})
        else:
            unmatched.append({**item, "reason": verdict.get("reason", "")})
    return {
        "required": required, "found_files": screenshots, "unreadable_files": unreadable,
        "matched": matched, "unmatched": unmatched,
        "shortfall": len(unmatched), "complete": not unmatched, "ai_reviewed": True,
        "images": images,
    }
