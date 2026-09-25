"""Deterministic (non-LLM) folder/file structure checker.

The submission guide's `required_paths` are LLM-authored per topic, but
whether a given path is actually PRESENT in the student's zip must never
depend on an LLM's read of the file list -- that's what let identical
resubmissions get different "folder not found" verdicts. This module is the
single source of truth for which required paths are present/missing;
zip_structure_validation_prompt (LLM) runs downstream of this and may only
add qualitative commentary (clutter, organization quality), never override
these presence/absence findings.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

# Matches Word/Google-Docs style auto-numbered heading prefixes: "2. ",
# "2.1 ", "2.1.3) ", "I. ", "A) ", possibly repeated ("2.1.3 " is one prefix
# of three numbered groups). A student's "2. Approach" heading and the
# submission guide's plain "Approach" requirement must be recognized as the
# same section without this stripped, they never will be.
_LEADING_NUMBERING_RE = re.compile(r"^\s*(?:[0-9]+|[ivxlcdm]+|[a-z])[.)]\s*(?=\S)", re.IGNORECASE)


def _normalize_heading(text: str) -> str:
    normalized = text.strip()
    # Numbering can nest ("2.1.3 Approach") -- strip repeatedly, not once.
    while True:
        stripped = _LEADING_NUMBERING_RE.sub("", normalized, count=1)
        if stripped == normalized:
            break
        normalized = stripped
    return normalized.strip().lower()


# What a student's .docx report needs is exactly these sections. "Code" and
# "Output Screenshots" used to be required too; they are not any more (the code
# is analysed from the zip, and screenshots are not part of a submission). But a
# submission guide is generated once per project and then stored, so guides
# issued before this change still list them -- these helpers strip the retired
# items at check time, so the older projects stop requiring them as well.
REPORT_SECTIONS = ["Problem Statement", "Approach", "Conclusion"]
_RETIRED_SECTIONS = {"code", "output screenshots", "screenshots", "output"}


def _is_retired_path(path: str) -> bool:
    return any("screenshot" in part for part in _normalize_parts(path))


def drop_retired_sections(required_sections: list[str] | None) -> list[str]:
    return [
        str(section) for section in required_sections or []
        if _normalize_heading(str(section)) not in _RETIRED_SECTIONS
    ]


def drop_retired_paths(required_paths: list[dict] | None) -> list[dict]:
    return [item for item in required_paths or [] if not _is_retired_path(str(item.get("path", "")))]


def drop_retired_tree_lines(folder_structure: list[str] | None) -> list[str]:
    return [line for line in folder_structure or [] if "screenshot" not in str(line).lower()]


def check_required_sections(required_sections: list[str] | None, doc_sections: dict[str, str] | None) -> dict:
    """required_sections: the submission guide's `docx_required_sections`
    (plain names, e.g. "Approach"). doc_sections: {heading_text: body_text}
    as returned by ingest_docx, where heading_text is the student's raw
    heading exactly as written (often auto-numbered, e.g. "2. Approach").

    Whether a required section actually EXISTS must never depend on an LLM's
    read of the heading list -- only content-quality judgment (is a present
    section's text substantive or placeholder) belongs to the LLM. Matches a
    required name against a normalized heading by equality or substring in
    either direction, so "Approach" matches "2. Approach" or "Approach &
    Design Rationale" alike.
    """
    normalized_headings = {_normalize_heading(heading): heading for heading in (doc_sections or {})}

    matched: list[str] = []
    missing: list[str] = []
    for required in required_sections or []:
        target = _normalize_heading(str(required))
        if not target:
            continue
        found = any(target == candidate or target in candidate or candidate in target for candidate in normalized_headings)
        (matched if found else missing).append(required)

    return {
        "is_complete": not missing,
        "matched_sections": matched,
        "missing_sections": missing,
    }


def _normalize_parts(path: str) -> list[str]:
    posix = PurePosixPath(path.replace("\\", "/"))
    return [part.lower() for part in posix.parts if part not in ("", "/")]


def check_required_paths(required_paths: list[dict] | None, zip_file_tree: list[str] | None) -> dict:
    """required_paths: [{"path": str, "type": "dir"|"file", "description": str}, ...]
    (from the submission guide's `required_paths`, see submission_guide_prompt).
    zip_file_tree: flat list of file paths as returned by ingest_zip.

    Matches on the required path's trailing segment (e.g. "src" out of
    "<slug>/src") against every path segment actually present in the zip --
    tolerant of the student naming their root folder differently than the
    suggested slug, since that's cosmetic, not a real omission.
    """
    entries = [_normalize_parts(p) for p in (zip_file_tree or [])]
    all_segments = {segment for parts in entries for segment in parts}
    all_basenames = {parts[-1] for parts in entries if parts}

    matched: list[dict] = []
    missing: list[dict] = []
    for item in required_paths or []:
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            continue
        item_type = str(item.get("type", "dir")).lower()
        parts = _normalize_parts(raw_path)
        if not parts:
            continue
        target = parts[-1]

        found = target in (all_basenames if item_type == "file" else all_segments)
        entry = {"path": raw_path, "type": item_type, "description": item.get("description", "")}
        (matched if found else missing).append(entry)

    return {
        "is_complete": not missing,
        "matched_items": matched,
        "missing_items": missing,
    }
