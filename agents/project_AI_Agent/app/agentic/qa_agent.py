"""Phase 4: a project-scoped Q&A agent with a real tool-calling loop.

Every other LLM call in this app (app/graph/nodes.py) is single-shot: one
fixed prompt, one JSON/text response, no iteration. This module is
deliberately different -- the model decides which tools to call, reads their
results, and can call more before answering, up to _MAX_TOOL_ITERATIONS
rounds. It exists so a student can ask "why did my code fail?" or "does
axios support this?" and get an answer actually grounded in THEIR submitted
project, not a generic reply.

Every tool here is scoped to one student's one project (loaded once per
question in ProjectContext, keyed off thread_id) -- there is no tool that
can read another student's data, and the system prompt explicitly instructs
the model to refuse questions unrelated to this project.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

import litellm

from app import config
from app.db.database import get_session
from app.db.models import ProjectAssignment, Submission
from app.ingestion.docx_ingest import DocxIngestError, ingest_docx
from app.ingestion.zip_ingest import ZipIngestError, ingest_zip
from app.llm.client import LLMError, call_text, record_usage

logger = logging.getLogger("capstone.qa_agent")

_MAX_TOOL_ITERATIONS = 4
_FILE_CHAR_LIMIT = 4000

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_project_brief",
            "description": "Get the student's chosen project topic, requirements, and required submission structure (folders, report sections).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_submitted_files",
            "description": "List the file paths in the student's most recently submitted zip.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_submitted_file",
            "description": "Read the text content of one specific file from the student's most recently submitted zip.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Exact path as returned by list_submitted_files."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_submitted_report_sections",
            "description": "Read the parsed section text of the student's most recently submitted .docx report.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_review",
            "description": "Get the most recent grading result and review report (structure/execution/output/code-quality) for this student's project.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web to verify a technical claim (a library, API, or concept referenced "
                "in the student's own code or report) or to check a current project requirement. "
                "Only use this when your own knowledge might be insufficient or outdated -- not for "
                "general chit-chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

_SYSTEM_PROMPT = """You are the Project Q&A Assistant for a DigiDARA capstone project.

You answer questions ONLY about the specific project the tools below give you access
to -- this one student's chosen topic, requirements, submitted code, submitted report,
and grading result. You have no other context and must not answer questions unrelated
to this project (general programming help unconnected to their submission, other
students' projects, unrelated topics) -- politely decline those and redirect the
student to ask about their own project instead.

Use the tools to ground every factual claim in what was actually submitted -- do not
guess at what the student's code does without reading it first. Use search_web only to
verify a technical claim referenced in their code/report or check a current
requirement, not for general chit-chat.

If the student attached extra material with their question (a screenshot description or
an uploaded document's text, given to you as ATTACHED MATERIAL below the question), treat
it as part of their question, not as something to fetch via a tool.

HANDLING A DISPUTE (the student disagrees with something the review flagged, e.g. "you
said my pie chart is missing but I did write it"):
1. First check the code directly. Call list_submitted_files, then read_submitted_file on
   whichever file(s) plausibly implement the disputed feature (e.g. the file that sets up
   a chart library, draws to a <canvas>, or renders the relevant UI section). Quote the
   specific evidence you find (or the specific absence of it) -- a real function/element/
   library call name, not a vague impression.
2. State plainly whether the code evidence CONFIRMS the student is right, CONFIRMS the
   original finding was right, or is genuinely INCONCLUSIVE from code alone (e.g. the code
   to draw a chart exists, but you can't tell from source alone whether it actually renders
   correctly at runtime).
3. Only if the code evidence is inconclusive AND the student has not yet attached
   anything (no ATTACHED MATERIAL present in this message), ask them to attach a
   screenshot that shows the specific disputed feature actually working on screen --
   name exactly what the screenshot needs to show, tied to their dispute. Do not ask for
   a screenshot if the code evidence already gives a clear enough answer, and do not ask
   again in the same reply if ATTACHED MATERIAL is already present -- use it instead.
4. Once a screenshot's description is available (as ATTACHED MATERIAL), combine it with
   the code evidence and give a clear final verdict: confirmed present, confirmed still
   missing, or still unclear and specifically why. Never just repeat the original
   verdict without engaging with the new evidence the student gave you.
This dispute-resolution flow is the ONLY thing this agent does differently from a plain
Q&A answer -- it never changes the actual stored grade/score; it only helps the student
understand or contest what was found, in this conversation.

Be concise, plain-language, and specific -- reference actual file names, section names,
or requirement text from the tools rather than speaking generically."""


class ProjectNotFound(LookupError):
    pass


class ProjectContext:
    """Loads everything the tools need once per question, from the DB plus
    the still-on-disk uploaded files for the most recent submission -- never
    from another student's records."""

    def __init__(self, thread_id: str):
        session = get_session()
        try:
            assignment = session.query(ProjectAssignment).filter_by(thread_id=thread_id).first()
            if assignment is None:
                raise ProjectNotFound(f"Unknown thread_id: {thread_id!r}")
            self.assignment_topic = assignment.topic_json
            self.assignment_about_markdown = assignment.about_markdown
            submission = (
                session.query(Submission)
                .filter_by(assignment_id=assignment.id)
                .order_by(Submission.submitted_at.desc())
                .first()
            )
            self.submission_paths = (submission.docx_path, submission.zip_path) if submission else None
            self.submission_status = submission.status.value if submission else None
            self.submission_score = submission.score_json if submission else None
            self.submission_feedback = submission.feedback_text if submission else None
            self.submission_review_markdown = submission.review_markdown if submission else None
        finally:
            session.close()

        self._zip_cache: dict | None = None
        self._docx_cache: dict | None = None

    def brief(self) -> dict:
        return {"topic": self.assignment_topic, "about_markdown": self.assignment_about_markdown}

    def _zip(self) -> dict:
        if self._zip_cache is None:
            if self.submission_paths is None:
                self._zip_cache = {"zip_file_tree": [], "zip_code_files": {}}
            else:
                try:
                    self._zip_cache = ingest_zip(self.submission_paths[1])
                except (ZipIngestError, OSError) as exc:
                    self._zip_cache = {"zip_file_tree": [], "zip_code_files": {}, "error": str(exc)}
        return self._zip_cache

    def _docx(self) -> dict:
        if self._docx_cache is None:
            if self.submission_paths is None:
                self._docx_cache = {"sections": {}}
            else:
                try:
                    self._docx_cache = ingest_docx(self.submission_paths[0])
                except (DocxIngestError, OSError) as exc:
                    self._docx_cache = {"sections": {}, "error": str(exc)}
        return self._docx_cache

    def list_files(self) -> list[str]:
        return self._zip().get("zip_file_tree", [])

    def read_file(self, path: str) -> str:
        code_files = self._zip().get("zip_code_files", {})
        if path not in code_files:
            return f"No such file in the submitted zip: {path!r}. Call list_submitted_files first to see valid paths."
        content = code_files[path]
        if len(content) > _FILE_CHAR_LIMIT:
            return content[:_FILE_CHAR_LIMIT] + f"\n... [truncated, {len(content)} chars total]"
        return content

    def report_sections(self) -> dict:
        return self._docx().get("sections", {})

    def latest_review(self) -> dict:
        if self.submission_paths is None:
            return {"status": "no submission yet"}
        return {
            "status": self.submission_status,
            "score": self.submission_score,
            "feedback": self.submission_feedback,
            "review_markdown": self.submission_review_markdown,
        }


def _run_web_search(query: str) -> str:
    """Reuses the same grounded search model as topic generation (see
    app.llm.client / config.WEB_SEARCH_LLM_MODEL) for a plain-text answer to
    one specific tool call."""
    try:
        return call_text(
            system="Answer the question directly and factually, in under 150 words, citing what you found.",
            user=query,
            web_search=True,
        )
    except LLMError as exc:
        return f"Web search failed: {exc}"


_TOOL_IMPLEMENTATIONS: dict[str, Callable[[ProjectContext, dict], Any]] = {
    "get_project_brief": lambda ctx, args: ctx.brief(),
    "list_submitted_files": lambda ctx, args: ctx.list_files(),
    "read_submitted_file": lambda ctx, args: ctx.read_file(str(args.get("path", ""))),
    "read_submitted_report_sections": lambda ctx, args: ctx.report_sections(),
    "get_latest_review": lambda ctx, args: ctx.latest_review(),
    "search_web": lambda ctx, args: _run_web_search(str(args.get("query", ""))),
}


def ask_project_question(thread_id: str, question: str, extra_context: str | None = None) -> dict:
    """Runs the tool-calling loop and returns {"answer": str, "tools_used": [str, ...]}.
    Raises ProjectNotFound if thread_id doesn't match a real assignment."""
    ctx = ProjectContext(thread_id)

    user_message = question
    if extra_context:
        user_message = f"{question}\n\nATTACHED MATERIAL (provided by the student alongside this question):\n{extra_context}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools_used: list[str] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = litellm.completion(
            model=config.LLM_MODEL,
            messages=messages,
            tools=_TOOLS,
            temperature=0.2,
        )
        message = response.choices[0].message
        record_usage(getattr(response, "usage", None), "qa_agent", config.LLM_MODEL)

        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return {"answer": (message.content or "").strip(), "tools_used": tools_used}

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [tool_call.model_dump() for tool_call in tool_calls],
        })
        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            implementation = _TOOL_IMPLEMENTATIONS.get(name)
            if implementation is None:
                result: Any = {"error": f"Unknown tool {name!r}"}
            else:
                tools_used.append(name)
                try:
                    result = implementation(ctx, args)
                except Exception as exc:  # a broken tool call must not crash the whole answer
                    logger.warning("qa_agent tool %s failed: %s", name, exc, exc_info=True)
                    result = {"error": str(exc)}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return {
        "answer": "I wasn't able to finish gathering enough information to answer confidently. "
        "Please try rephrasing your question or asking about one specific part of your project.",
        "tools_used": tools_used,
    }
