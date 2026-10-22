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
# "Output Screenshots" used to be required REPORT sections too; they are not any
# more -- the code is analysed from the zip, and the output screenshots are image
# files in the zip's output_screenshots folder, not pictures pasted into the
# report. A submission guide is generated once per project and then stored, so
# guides issued earlier still list those two as report sections; this strips
# them at check time so older projects stop requiring them in the .docx as well.
# (The zip's output_screenshots FOLDER is still required -- see screenshots.py.)
REPORT_SECTIONS = ["Problem Statement", "Approach", "Conclusion"]
_RETIRED_SECTIONS = {"code", "output screenshots", "screenshots", "output"}


def drop_retired_sections(required_sections: list[str] | None) -> list[str]:
    return [
        str(section) for section in required_sections or []
        if _normalize_heading(str(section)) not in _RETIRED_SECTIONS
    ]


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


_SOURCE_DIRS = {"src", "source", "sources", "code", "app", "lib", "backend", "frontend", "server", "client", "main"}
_TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "testing"}
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".rs", ".kt", ".swift", ".dart", ".vue", ".svelte", ".html", ".ipynb", ".sql", ".sh",
}
_TEST_FILE_RE = re.compile(
    r"(^test_.+\.py$|.+_test\.(py|go)$|.+\.(test|spec)\.[cm]?[jt]sx?$|^test.*\.java$|.+tests?\.(java|kt|cs)$|.+_spec\.rb$)",
    re.IGNORECASE,
)


def _loose(name: str) -> str:
    """"Output_Screenshots", "output-screenshot" and "outputscreenshots" are the same folder."""
    squashed = re.sub(r"[^a-z0-9]", "", name.lower())
    return squashed[:-1] if squashed.endswith("s") else squashed


def _role(target: str) -> str | None:
    if target in _SOURCE_DIRS:
        return "source"
    if target in _TEST_DIRS:
        return "tests"
    if "screenshot" in target or target in {"output", "outputs"}:
        return "screenshots"
    return None


def check_required_paths(
    required_paths: list[dict] | None, zip_file_tree: list[str] | None, screenshots_found: bool | None = None,
) -> dict:
    """required_paths: [{"path": str, "type": "dir"|"file", "description": str}, ...]
    (from the submission guide's `required_paths`, see submission_guide_prompt).
    zip_file_tree: flat list of file paths as returned by ingest_zip.
    screenshots_found: whether ingest found any screenshot images anywhere in the zip.

    A required folder counts as present when the zip holds what belongs in it,
    whatever the folder is called or how deep it sits:
    - a source folder ("src", ...): any source code file in the zip;
    - a tests folder: a tests/test folder or any test file (test_x.py, x.test.js, ...);
    - the screenshots folder: any screenshot image in the zip;
    - any other folder: a folder with that name, ignoring case, "-", "_" and a plural "s".
    A required file matches by file name, ignoring case.
    """
    entries = [_normalize_parts(p) for p in (zip_file_tree or [])]
    all_segments = {segment for parts in entries for segment in parts[:-1]}
    loose_segments = {_loose(segment) for segment in all_segments}
    all_basenames = {parts[-1] for parts in entries if parts}
    has_source = any(PurePosixPath(name).suffix in _SOURCE_EXTENSIONS for name in all_basenames)
    has_tests = bool(all_segments & _TEST_DIRS) or any(_TEST_FILE_RE.match(name) for name in all_basenames)
    has_screenshot_folder = any("screenshot" in segment for segment in all_segments)

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

        if item_type == "file":
            found = target in all_basenames
        else:
            role = _role(target)
            found = target in all_segments or _loose(target) in loose_segments
            if role == "source":
                found = found or has_source
            elif role == "tests":
                found = found or has_tests
            elif role == "screenshots":
                found = found or has_screenshot_folder or bool(screenshots_found)
        entry = {"path": raw_path, "type": item_type, "description": item.get("description", "")}
        (matched if found else missing).append(entry)

    return {
        "is_complete": not missing,
        "matched_items": matched,
        "missing_items": missing,
    }
