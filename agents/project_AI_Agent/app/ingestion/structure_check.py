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

from pathlib import PurePosixPath


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
