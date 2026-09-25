"""Turns "something expected is missing" into a clear, specific instruction.

A student who is told only "src folder is missing" or "Approach section
missing" is left guessing what belongs there, where it goes and how to fix it.
Everything here is built deterministically from facts the checkers already
established (which report sections were absent, which required paths were
absent, which requirements the code doesn't implement) -- never from an LLM's
paraphrase of them -- and each message says WHAT is missing, WHAT belongs in
it, and WHAT to do about it.
"""
from __future__ import annotations

from typing import Any

from app.ingestion.screenshots import screenshot_status
from app.ingestion.structure_check import _normalize_heading

_SECTION_GUIDANCE = {
    "problem statement": (
        "describe the problem your project solves and who has it, then list the requirements the project has to meet."
    ),
    "approach": (
        "explain how you built it: the main parts (files or modules) and what each one does, the key design "
        "decisions and why you made them, and how your code meets each requirement. Explain it in words - do not paste code."
    ),
    "conclusion": (
        "summarise what you built and whether it meets the requirements, what you learned, and its limitations "
        "or possible improvements."
    ),
}


def explain_missing_section(name: str) -> str:
    guidance = _SECTION_GUIDANCE.get(
        _normalize_heading(name),
        "write a substantive explanation under it (several full sentences, not a single line).",
    )
    return (
        f'**The "{name}" section is missing from your report.** Add a heading named "{name}" '
        f"(use Word's Heading 1 style so it is recognised) and {guidance}"
    )


def explain_weak_section(entry: str) -> str:
    """`entry` is the structure reviewer's "<section>: <reason>" for a section
    that exists but is placeholder-thin."""
    name, _, reason = entry.partition(":")
    name, reason = name.strip(), reason.strip()
    if not reason:
        return f'**The "{name}" section needs more detail.** Expand it with real explanation, not a line or two.'
    return f'**The "{name}" section needs more detail.** {reason}'


def explain_missing_path(item: dict[str, Any]) -> str:
    """One required folder/file that is absent from the zip."""
    path = str(item.get("path", "")).strip()
    is_file = str(item.get("type", "dir")).lower() == "file"
    kind = "file" if is_file else "folder"
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or path
    description = str(item.get("description", "")).strip().rstrip(".")

    parts = [f'**Your zip has no "{name}" {kind}.** The checker looked for {path}.']
    if description:
        parts.append(f"It should contain: {description}.")
    if is_file:
        parts.append(f"Add the file at {path}, then zip the project again.")
    else:
        parts.append(
            f'Create a folder named "{name}" inside your project\'s root folder, move the matching files into it, '
            f"then zip the project again so the layout is {path}/..."
        )
    return " ".join(parts)


def explain_requirement(check: dict[str, Any]) -> str:
    """One functional requirement the code does not (fully) implement."""
    requirement = str(check.get("requirement", "")).strip()
    evidence = str(check.get("evidence", "")).strip().rstrip(".")
    partial = check.get("status") == "partial"
    lead = "is only partly implemented" if partial else "is not implemented"
    text = f'**Requirement {lead}:** "{requirement}".'
    if evidence:
        text += f" {evidence[0].upper()}{evidence[1:]}."
    text += " Add or finish this in the file where it belongs, then upload the zip again."
    return text


def missing_path_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    detail = (state.get("zip_structure_score") or {}).get("required_paths_detail") or {}
    return list(detail.get("missing_items") or [])


def unmet_requirements(state: dict[str, Any]) -> list[dict[str, Any]]:
    checks = (state.get("output_verification") or {}).get("requirements_check") or []
    return [check for check in checks if check.get("status") != "met"]


def explain_missing_screenshots(status: dict[str, Any]) -> str | None:
    """Which output screenshots the project needs, and what the zip has instead.

    The student is given every required screenshot by file name, module and what
    must be visible in it -- never just "screenshots missing"."""
    if status["complete"]:
        return None
    required, found = status["required"], status["found_files"]
    have = (
        f"Your output_screenshots folder has {len(found)} readable image(s): {', '.join(found)}."
        if found else "Your zip has no readable screenshot images in an output_screenshots folder."
    )
    lines = [
        f"**Output screenshots are missing: this project needs {len(required)}, and your zip has {len(found)}.** {have}",
        "Save ONE image file per item below inside the output_screenshots folder of your zip (not in the .docx report), then zip again:",
    ]
    if status["matched"]:
        lines.append("Already found by file name: " + ", ".join(item["filename"] for item in status["matched"]) + ".")
    for item in status["unmatched"] or required:
        module = f" [{item['module']}]" if item.get("module") else ""
        capture = f" How to capture it: {item['how_to_capture']}" if item.get("how_to_capture") else ""
        lines.append(f"  - {item['filename']}{module}: {item['description']}.{capture}")
    if status["unreadable_files"]:
        lines.append("These files are in the folder but could not be read as images: " + ", ".join(status["unreadable_files"]) + ".")
    return "\n".join(lines)


def revision_items(state: dict[str, Any]) -> list[str]:
    """Everything wrong with the report and the zip layout, each as one clear
    instruction. Syntax errors are NOT here -- they travel as structured data."""
    structure = state.get("structure_score") or {}
    items = [explain_missing_section(name) for name in structure.get("missing_sections") or []]
    items += [explain_weak_section(entry) for entry in structure.get("weak_sections") or []]
    screenshots = explain_missing_screenshots(
        screenshot_status(state.get("submission_guide") or {}, state.get("screenshot_evidence")))
    # The folder itself missing is one problem, not two: the screenshots message already
    # says where they go, so its generic "no output_screenshots folder" line is dropped.
    paths = [item for item in missing_path_items(state) if not (screenshots and "screenshot" in str(item.get("path", "")).lower())]
    items += [explain_missing_path(item) for item in paths]
    if screenshots:
        items.append(screenshots)
    # A report that was judged incomplete but with nothing specific listed:
    # fall back to the reviewer's own note rather than saying nothing.
    if not items and structure.get("is_complete") is False and structure.get("notes"):
        items.append(str(structure["notes"]).strip())
    return items


def fix_list(state: dict[str, Any]) -> list[str]:
    """What to change in the CODE/zip after a failed grade: requirements the
    code doesn't implement, plus any required file or folder that's absent."""
    return [explain_requirement(check) for check in unmet_requirements(state)] + [
        explain_missing_path(item) for item in missing_path_items(state)
    ]  # (screenshots are gated before scoring, so a graded submission always has them)


def as_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
