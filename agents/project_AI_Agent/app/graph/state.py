from typing import Any, TypedDict


class ProjectAgentState(TypedDict, total=False):
    # Linking fields back to the relational DB (not in the original spec's
    # state sketch, but required to persist/resume across HTTP requests).
    student_id: str
    course_id: str
    assignment_id: str
    submission_id: str

    student_name: str
    phone: str
    course_name: str
    course_medium: str  # "local" | "api"
    difficulty: str  # "easy" | "medium" | "hard" — free-topic requests only; defaults to "easy"

    # There is no certificate/enrollment gate -- every request is a free-topic
    # request. `course_name` here is actually the student's free-text
    # description (role/company/domain/technology), not a real completed
    # course — topic_generator_prompt and topic_generator_node both need to
    # know this so they frame it as the student's own brief (and the primary
    # steering signal) instead of "a course they finished", and skip the
    # random generic angle_hint that's meant to add variety to an otherwise-
    # underspecified real course, not override an already-specific request.
    free_topic_request: bool

    topic_options: list[dict[str, Any]]  # [{id, title, summary, medium, skills_applied}]
    chosen_topic: dict[str, Any]
    requirements: dict[str, Any]  # RequirementExpansionNode output
    deadline_at: str

    submission_guide: dict[str, Any]  # SubmissionGuideNode output
    # Plain-language "about this project" doc, built alongside submission_guide
    # (see app/graph/report.py) -- downloadable via GET /api/assignment/{thread_id}/about.md
    about_markdown: str

    docx_path: str
    doc_sections: dict[str, str]
    structure_score: dict[str, Any]  # StructureValidationNode output

    zip_path: str
    zip_file_tree: list[str]
    zip_code_files: dict[str, str]
    zip_structure_score: dict[str, Any]  # ZipStructureValidationNode output
    # The output screenshots found in the zip (see app/ingestion/screenshots.py):
    # {files, valid_files, ocr_text}. Only valid_files count towards the guide's
    # required_screenshots.
    screenshot_evidence: dict[str, Any]
    # SyntaxCheckNode output -- real-parser results over the zip's Python/JSON/
    # TOML files: {checked_files, checked_languages, unchecked_extensions,
    # errors[{path, language, line, column, message, source_line}], error_count,
    # has_errors}. Errors here send the submission back before any scoring.
    syntax_report: dict[str, Any]

    # CodeExecutionNode output — best-effort, sandboxed (Judge0) run of the
    # submission's detected Python entry point. {"available": False, "reason": ...}
    # when there's no runnable entry point or Judge0 isn't reachable; never a
    # hard gate downstream, just supplementary evidence.
    execution_result: dict[str, Any]

    output_verification: dict[str, Any]
    code_quality_score: dict[str, Any]

    final_score: float
    passed: bool  # deterministic final_score >= config.PASS_THRESHOLD, decided in ScoreAggregatorNode
    score_reasoning: str
    feedback: str
    # Full plain-language review report (see app/graph/report.py), built after
    # every submission attempt -- downloadable via GET /api/submission/{id}/review.md
    review_markdown: str

    status: str  # routes control flow / mirrors AssignmentStatus or SubmissionStatus
    revision_notes: str
