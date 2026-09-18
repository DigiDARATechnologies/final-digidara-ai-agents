"""Builds the two student-facing Markdown documents from state that the
graph nodes already computed:

- `build_about_markdown` -- generated once the submission guide is ready.
  What the project is, what to build, and exactly what folder/file structure
  and report sections are required. The student's one canonical reference,
  also useful to bring to the viva.
- `build_review_markdown` -- generated after a submission attempt. A full,
  plain-language checklist of what passed/failed and why, replacing "check
  the JSON scores yourself" with something a first-time submitter can read
  and act on directly.

Both are safe to call with a partially-populated state: a submission
rejected at the docx-structure gate never reaches code_execution/scoring,
so those sections just render empty rather than raising.
"""
from __future__ import annotations

from typing import Any


def _checkbox(ok: bool) -> str:
    return "✅" if ok else "❌"


def _structure_section(state: dict[str, Any]) -> list[str]:
    structure = state.get("structure_score") or {}
    lines = ["## Report Structure (.docx)"]
    lines.append(f"{_checkbox(bool(structure.get('is_complete', True)))} All required report sections present and substantive")
    for section in structure.get("missing_sections") or []:
        lines.append(f"- ❌ Missing section: **{section}**")
    for weak in structure.get("weak_sections") or []:
        lines.append(f"- ⚠️ Weak section: {weak}")
    screenshots_present = structure.get("screenshots_present")
    if screenshots_present is not None:
        lines.append(f"{_checkbox(bool(screenshots_present))} Output screenshots embedded in the report")
    if structure.get("notes"):
        lines.append("")
        lines.append(structure["notes"])
    return lines


def _zip_structure_section(state: dict[str, Any]) -> list[str]:
    zip_score = state.get("zip_structure_score") or {}
    detail = zip_score.get("required_paths_detail") or {}
    matched = detail.get("matched_items") or []
    missing = detail.get("missing_items") or []

    lines = ["## Folder & File Structure (.zip)"]
    if not matched and not missing:
        lines.append("_No required-path checklist was available for this submission._")
    for item in matched:
        lines.append(f"- ✅ `{item['path']}` — {item.get('description') or 'present'}")
    for item in missing:
        description = item.get("description") or ""
        lines.append(
            f"- ❌ `{item['path']}` — MISSING. {description} "
            f"Add this {item.get('type', 'folder')} to your zip and resubmit."
        )
    if zip_score.get("structure_quality"):
        lines.append("")
        lines.append(f"Organization quality: **{zip_score['structure_quality']}**")
    for flag in zip_score.get("clutter_flags") or []:
        lines.append(f"- ⚠️ Clutter: {flag}")
    if zip_score.get("notes"):
        lines.append("")
        lines.append(zip_score["notes"])
    return lines


def _execution_section(state: dict[str, Any]) -> list[str]:
    execution = state.get("execution_result")
    if execution is None:
        return []
    lines = ["## Code Execution"]
    if not execution.get("available"):
        lines.append(f"_Not run: {execution.get('reason', 'no runnable entry point detected')}._")
        return lines

    if execution.get("kind") == "browser":
        errors = execution.get("console_errors") or []
        page_errors = execution.get("page_errors") or []
        lines.append(
            f"{_checkbox(not errors and not page_errors)} Loaded `{execution.get('entry_point')}` in a headless browser"
        )
        lines.append(f"- Page title: {execution.get('page_title') or '(empty)'}")
        if errors:
            lines.append(f"- Console errors: {errors}")
        if page_errors:
            lines.append(f"- Page errors: {page_errors}")
    else:
        lines.append(
            f"{_checkbox(bool(execution.get('completed')))} Ran `{execution.get('entry_point')}` "
            f"— status: {execution.get('status')}"
        )
        if execution.get("stderr"):
            lines.append(f"- stderr: {execution['stderr']}")
    return lines


def _output_verification_section(state: dict[str, Any]) -> list[str]:
    verification = state.get("output_verification")
    if verification is None:
        return []
    lines = ["## Output Verification"]
    lines.append(
        f"{_checkbox(bool(verification.get('output_correct')))} Output matches the project requirements "
        f"(confidence: {verification.get('confidence', 'unknown')})"
    )
    for req in verification.get("requirements_demonstrated") or []:
        lines.append(f"- {req}")
    for issue in verification.get("issues_found") or []:
        lines.append(f"- ⚠️ {issue}")
    if verification.get("notes"):
        lines.append("")
        lines.append(verification["notes"])
    return lines


_CODE_QUALITY_AXES = [
    ("structure_score", "Structure", "How your code is organized into functions/files."),
    ("syntax_score", "Syntax", "Correctness and consistency of the code itself."),
    ("maintainability_score", "Maintainability", "Naming, comments, error handling."),
    ("completeness_score", "Completeness vs brief", "Whether it does what was asked, no more/less."),
]


def _code_quality_section(state: dict[str, Any]) -> list[str]:
    quality = state.get("code_quality_score")
    if quality is None:
        return []
    lines = ["## Code Quality (0-25 each, /100 total)"]
    for key, label, blurb in _CODE_QUALITY_AXES:
        value = quality.get(key)
        if value is not None:
            lines.append(f"- **{label}: {value}/25** — {blurb}")
    if quality.get("total_code_score") is not None:
        lines.append("")
        lines.append(f"**Total code score: {quality['total_code_score']}/100**")
    for point in quality.get("strengths") or []:
        lines.append(f"- \U0001f44d {point}")
    for point in quality.get("weaknesses") or []:
        lines.append(f"- \U0001f44e {point}")
    for point in quality.get("specific_line_feedback") or []:
        lines.append(f"- \U0001f50e {point}")
    return lines


def build_review_markdown(state: dict[str, Any]) -> str:
    topic_title = (state.get("chosen_topic") or {}).get("title", "Your project")
    status = state.get("status")
    passed = state.get("passed")
    final_score = state.get("final_score")

    if status == "needs_revision" and final_score is None:
        verdict = "⏸️ SUBMISSION INCOMPLETE — fix the items below and resubmit"
    elif passed:
        verdict = f"✅ PASSED — {final_score}/100"
    elif passed is False:
        verdict = f"❌ NEEDS REVISION — {final_score}/100"
    else:
        verdict = "Processing"

    lines = [f"# Project Review — {topic_title}", "", f"**Result: {verdict}**", ""]
    lines += _structure_section(state) + [""]
    lines += _zip_structure_section(state) + [""]
    lines += _execution_section(state) + [""]
    lines += _output_verification_section(state) + [""]
    lines += _code_quality_section(state) + [""]

    if state.get("score_reasoning"):
        lines += ["## Overall Reasoning", state["score_reasoning"], ""]

    revision_notes = state.get("revision_notes")
    if revision_notes:
        lines += ["## What To Fix Before Resubmitting", revision_notes, ""]
    elif passed:
        lines += [
            "## Next Step",
            "Your code review passed. Complete the viva (oral defense) to finish certification.",
            "",
        ]

    return "\n".join(lines).strip() + "\n"


def build_about_markdown(state: dict[str, Any]) -> str:
    topic = state.get("chosen_topic") or {}
    requirements = state.get("requirements") or {}
    guide = state.get("submission_guide") or {}

    lines = [f"# About This Project — {topic.get('title', 'Untitled')}", ""]
    if topic.get("summary"):
        lines += [topic["summary"], ""]
    if requirements.get("objective"):
        lines += ["## Objective", requirements["objective"], ""]

    lines.append("## What You Need To Build")
    for req in requirements.get("functional_requirements") or []:
        lines.append(f"- {req}")
    lines.append("")

    if requirements.get("technical_constraints"):
        lines.append("## Constraints")
        for constraint in requirements["technical_constraints"]:
            lines.append(f"- {constraint}")
        lines.append("")

    lines.append("## What To Submit")
    for deliverable in requirements.get("expected_deliverables") or []:
        lines.append(f"- {deliverable}")
    lines.append("")

    lines.append("## Required Folder Structure (inside the .zip)")
    for tree_line in guide.get("folder_structure") or []:
        lines.append(f"    {tree_line}")
    lines.append("")
    for item in guide.get("required_paths") or []:
        lines.append(f"- `{item.get('path')}` ({item.get('type')}) — {item.get('description', '')}")
    lines.append("")

    lines.append("## Required Sections In Your .docx Report")
    for index, section in enumerate(guide.get("docx_required_sections") or [], start=1):
        lines.append(f"{index}. {section}")
    lines.append("")

    if guide.get("worked_example_section"):
        lines += [
            f"## Example: {guide['worked_example_section']}",
            guide.get("worked_example_text", ""),
            "",
        ]

    if guide.get("common_mistakes"):
        lines.append("## Common Mistakes To Avoid")
        for mistake in guide["common_mistakes"]:
            lines.append(f"- {mistake}")
        lines.append("")

    if requirements.get("evaluation_criteria_summary"):
        lines.append("## How This Is Evaluated")
        for criterion in requirements["evaluation_criteria_summary"]:
            lines.append(f"- {criterion}")
        lines.append("")

    if state.get("deadline_at"):
        lines.append(f"**Submission deadline:** {state['deadline_at']}")

    return "\n".join(lines).strip() + "\n"
