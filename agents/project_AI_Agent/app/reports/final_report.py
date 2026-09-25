"""The final project report (a PDF) a student gets after passing BOTH the code
score and the viva.

`assemble_report_data` turns what grading already stored (the assignment, the
student, the submission's score/feedback/viva rows) into one plain dict, and
`build_final_report_pdf` renders that dict. Keeping them apart means the layout
can be tested without a database and the data can be tested without a PDF.

Every page carries the DigiDARA Technologies logo. Text is limited to what the
PDF's standard fonts can draw (Latin-1 / Windows-1252): anything else a student
typed in their viva answers is shown as "?" rather than as a broken glyph.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.viva import VIVA_ATTEMPTS, VIVA_PASS_PERCENT

LOGO = Path(__file__).resolve().parents[1] / "assets" / "digidara-technologies-logo.png"

BRAND_BLUE = colors.HexColor("#004AAD")
INK = colors.HexColor("#101828")
MUTED = colors.HexColor("#475467")
RULE = colors.HexColor("#D0D5DD")
GREEN, AMBER, RED = "#067647", "#B54708", "#B42318"
PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X
HEADER_H = 38 * mm
LOGO_W = 58 * mm

_MAX_ANSWER_CHARS = 380
_MAX_EVIDENCE_CHARS = 260
_MAX_FILES_LISTED = 40


# --------------------------------------------------------------- text helpers --

def _plain(value: Any, limit: int | None = None) -> str:
    """Single-line, Latin-1-safe text (unsupported characters become '?')."""
    text = " ".join(("" if value is None else str(value)).split())
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text.encode("cp1252", "replace").decode("cp1252")


def _markup(value: Any, limit: int | None = None) -> str:
    """`_plain`, XML-escaped for Paragraph, with **bold** and `code` turned into tags."""
    text = escape(_plain(value, limit))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)


def _when(value: Any) -> str:
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    return _plain(value) or "-"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:60] or "Project"


def report_filename(project_title: str) -> str:
    return f"Capstone_Report_{_slug(_plain(project_title))}.pdf"


# ----------------------------------------------------------------- data ------

def assemble_report_data(assignment: Any, student: Any, submission: Any, pass_mark: float, viva_pass_mark: int) -> dict[str, Any]:
    from app.viva import viva_rating

    """Everything the report shows, from the stored rows. Missing pieces (an
    older submission that predates a field) simply come back empty."""
    score = dict(submission.score_json or {})
    topic = dict(assignment.topic_json or {})
    requirements = dict(assignment.requirements_json or {})
    questions = list(submission.viva_questions_json or [])
    answers = {item.get("question_id"): item for item in list(submission.viva_answers_json or [])}
    viva = []
    for index, question in enumerate(questions, start=1):
        given = answers.get(question.get("id"), {})
        viva.append({
            "number": index, "question": question.get("question", ""),
            "answer": given.get("answer", ""), "correct": bool(given.get("correct")), "note": given.get("note", ""),
        })
    attempts = [
        {"attempt": a.get("attempt", n), "rating": a.get("rating") or viva_rating(a.get("correct", 0), a.get("total", 0)),
         "passed": bool(a.get("passed"))}
        for n, a in enumerate(list(submission.viva_attempts_json or []), start=1)
    ]
    if not attempts and submission.viva_score is not None:   # graded before attempts were recorded
        attempts = [{"attempt": 1, "rating": viva_rating(int(submission.viva_score), len(questions) or 10),
                     "passed": bool(submission.viva_passed)}]
    verification = dict(score.get("output_verification") or {})
    syntax = dict(score.get("syntax_report") or {})
    return {
        "report_id": submission.id,
        "student_name": getattr(student, "name", "") or "Student",
        "project_title": topic.get("title", "Capstone project"),
        "project_summary": topic.get("summary", ""),
        "objective": requirements.get("objective", ""),
        "functional_requirements": requirements.get("functional_requirements") or [],
        "technical_constraints": requirements.get("technical_constraints") or [],
        "submitted_at": submission.submitted_at, "deadline_at": assignment.deadline_at, "generated_at": datetime.now(timezone.utc),
        "final_score": score.get("final_score"), "pass_mark": pass_mark, "passed": bool(score.get("passed")),
        "viva_score": submission.viva_score, "viva_total": len(questions) or 10, "viva_pass_mark": viva_pass_mark,
        "viva_passed": bool(submission.viva_passed), "viva_pass_percent": VIVA_PASS_PERCENT,
        "viva_attempts": attempts, "viva_rating": attempts[-1]["rating"] if attempts else "-",
        "code_quality": dict(score.get("code_quality_score") or {}),
        "requirements_check": verification.get("requirements_check") or [],
        "constraints_check": verification.get("constraints_check") or [],
        "screenshots_check": verification.get("screenshots_check") or [],
        "screenshot_files": (score.get("screenshot_evidence") or {}).get("valid_files") or [],
        "syntax": {"checked": len(syntax.get("checked_files") or []), "languages": syntax.get("checked_languages") or [],
                   "errors": syntax.get("error_count") or 0},
        "report_sections": (score.get("structure_score") or {}).get("matched_sections") or [],
        "submitted_files": score.get("submitted_files") or [],
        "feedback": submission.feedback_text or "", "score_reasoning": score.get("score_reasoning") or "",
        "viva": viva,
    }


# ------------------------------------------------------------------ layout ---

class _NumberedCanvas(pdf_canvas.Canvas):
    """Draws the logo, a rule and a 'Page X of Y' footer on EVERY page. The total
    is only known once the last page exists, so pages are held back until save()."""

    footer_text = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pages: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802 (reportlab's name)
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._furniture(total)
            super().showPage()
        super().save()

    def _furniture(self, total: int) -> None:
        self.saveState()
        logo = ImageReader(str(LOGO))
        width, height = logo.getSize()
        drawn_h = LOGO_W * height / width
        self.drawImage(logo, MARGIN_X, PAGE_H - 11 * mm - drawn_h, width=LOGO_W, height=drawn_h, mask="auto")
        self.setStrokeColor(BRAND_BLUE)
        self.setLineWidth(1.2)
        self.line(MARGIN_X, PAGE_H - HEADER_H + 3 * mm, PAGE_W - MARGIN_X, PAGE_H - HEADER_H + 3 * mm)
        self.setStrokeColor(RULE)
        self.setLineWidth(0.6)
        self.line(MARGIN_X, 16 * mm, PAGE_W - MARGIN_X, 16 * mm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 8.5)
        self.drawString(MARGIN_X, 11 * mm, self.footer_text)
        self.drawRightString(PAGE_W - MARGIN_X, 11 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14.5,
                          textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5)
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=21, leading=26,
                                textColor=BRAND_BLUE, alignment=0, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=body, fontSize=12, leading=16, textColor=MUTED, alignment=0, spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=13.5, leading=18,
                             textColor=BRAND_BLUE, spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                             textColor=INK, spaceBefore=6, spaceAfter=3),
        "body": body,
        "cell": ParagraphStyle("cell", parent=body, fontSize=9, leading=12, alignment=0, spaceAfter=0),
        "cellb": ParagraphStyle("cellb", parent=body, fontSize=9, leading=12, alignment=0, spaceAfter=0, fontName="Helvetica-Bold"),
        "small": ParagraphStyle("small", parent=body, fontSize=8.5, leading=11.5, textColor=MUTED, alignment=0, spaceAfter=2),
        "mono": ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=8, leading=10.5, alignment=0, spaceAfter=0),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3),
        "big": ParagraphStyle("big", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=21, alignment=1, spaceAfter=0),
        "tiny": ParagraphStyle("tiny", parent=body, fontSize=8, leading=10.5, textColor=MUTED, alignment=1, spaceAfter=0),
    }


def _table(rows: list[list[Any]], widths: list[float], header: bool = True, zebra: bool = True) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF4FF")), ("LINEBELOW", (0, 0), (-1, 0), 0.9, BRAND_BLUE)]
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")])]
    table.setStyle(TableStyle(style))
    return table


def _bullets(items: list[Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [Paragraph(_markup(item), styles["bullet"], bulletText="•") for item in items if str(item).strip()]


def _rich(text: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Model-written feedback: '### heading', '- bullet' and plain lines."""
    flowables: list[Any] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            flowables.append(Paragraph(_markup(stripped.lstrip("# ")), styles["h2"]))
        elif stripped[:2] in ("- ", "* "):
            flowables.append(Paragraph(_markup(stripped[2:]), styles["bullet"], bulletText="•"))
        else:
            flowables.append(Paragraph(_markup(stripped), styles["body"]))
    return flowables


_STATUS = {
    "met": ("Met", GREEN), "partial": ("Partly met", AMBER), "not_met": ("Not met", RED),
    "present": ("Present", GREEN), "unclear": ("Unclear", AMBER), "missing": ("Missing", RED),
}


def _status(value: Any) -> str:
    label, color = _STATUS.get(str(value), (_plain(value) or "-", "#475467"))
    return f'<font color="{color}"><b>{escape(label)}</b></font>'


def _banner(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    ok = data["passed"] and data["viva_passed"]
    tone = GREEN if ok else RED

    def cell(label: str, value: str, note: str) -> list[Paragraph]:
        return [Paragraph(label, styles["tiny"]), Paragraph(f'<font color="{tone}">{value}</font>', styles["big"]), Paragraph(note, styles["tiny"])]

    score = data["final_score"]
    score_text = f"{score:g} / 100" if isinstance(score, (int, float)) else "-"
    viva_text = str(data.get("viva_rating") or "-").upper()
    table = Table([[
        cell("OVERALL RESULT", "PASSED" if ok else "NOT PASSED", "code score and viva both passed" if ok else "see the sections below"),
        cell("CODE SCORE", score_text, f"pass mark {data['pass_mark']:g}"),
        cell("VIVA", viva_text, f"at least {data.get('viva_pass_percent', VIVA_PASS_PERCENT)}% correct to pass"),
    ]], colWidths=[CONTENT_W / 3] * 3)
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(tone)), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6FEF9" if ok else "#FEF3F2")),
        ("LINEAFTER", (0, 0), (1, 0), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


_AXES = [
    ("structure_score", "Structure", "How the code is organised into functions, files and modules."),
    ("syntax_score", "Syntax", "Correctness and consistency of the code itself."),
    ("maintainability_score", "Maintainability", "Naming, comments, error handling."),
    ("completeness_score", "Completeness", "Whether it does what the project brief asked."),
]


def build_final_report_pdf(data: dict[str, Any]) -> bytes:
    styles = _styles()
    story: list[Any] = [
        Paragraph("Capstone Project Completion Report", styles["title"]),
        Paragraph(_markup(data["project_title"]), styles["subtitle"]),
        _banner(data, styles),
        Spacer(1, 10),
    ]

    details = [
        ("Student", data["student_name"]), ("Project", data["project_title"]),
        ("Submitted", _when(data["submitted_at"])), ("Submission deadline", _when(data["deadline_at"])),
        ("Report generated", _when(data["generated_at"])), ("Report ID", data["report_id"]),
    ]
    story.append(_table([[Paragraph(_markup(k), styles["cellb"]), Paragraph(_markup(v), styles["cell"])] for k, v in details],
                        [CONTENT_W * 0.28, CONTENT_W * 0.72], header=False, zebra=False))

    story.append(Paragraph("1. Project overview", styles["h1"]))
    if data["project_summary"]:
        story.append(Paragraph(_markup(data["project_summary"]), styles["body"]))
    if data["objective"]:
        story.append(Paragraph("Objective", styles["h2"]))
        story.append(Paragraph(_markup(data["objective"]), styles["body"]))
    if data["technical_constraints"]:
        story.append(Paragraph("Technical constraints", styles["h2"]))
        story += _bullets(data["technical_constraints"], styles)

    story.append(Paragraph("2. Requirements and how the code meets them", styles["h1"]))
    checks = data["requirements_check"]
    if checks:
        rows = [[Paragraph(h, styles["cellb"]) for h in ("Requirement", "Result", "Where it is implemented")]]
        rows += [[Paragraph(_markup(c.get("requirement")), styles["cell"]), Paragraph(_status(c.get("status")), styles["cell"]),
                  Paragraph(_markup(c.get("evidence"), _MAX_EVIDENCE_CHARS), styles["cell"])] for c in checks]
        story.append(_table(rows, [CONTENT_W * 0.36, CONTENT_W * 0.14, CONTENT_W * 0.50]))
    else:
        story += _bullets(data["functional_requirements"], styles)
    if data["constraints_check"]:
        story.append(Paragraph("Technical constraints", styles["h2"]))
        story += _bullets(data["constraints_check"], styles)

    quality = data["code_quality"]
    story.append(Paragraph("3. Code quality", styles["h1"]))
    rows = [[Paragraph(h, styles["cellb"]) for h in ("Area", "Score", "What it measures")]]
    rows += [[Paragraph(label, styles["cellb"]), Paragraph(f"{quality[key]} / 25", styles["cell"]), Paragraph(blurb, styles["cell"])]
             for key, label, blurb in _AXES if quality.get(key) is not None]
    if quality.get("total_code_score") is not None:
        rows.append([Paragraph("Total", styles["cellb"]), Paragraph(f"<b>{quality['total_code_score']} / 100</b>", styles["cell"]), Paragraph("", styles["cell"])])
    if len(rows) > 1:
        story.append(_table(rows, [CONTENT_W * 0.22, CONTENT_W * 0.16, CONTENT_W * 0.62]))
    if quality.get("strengths"):
        story.append(Paragraph("Strengths", styles["h2"]))
        story += _bullets(quality["strengths"], styles)
    if quality.get("weaknesses"):
        story.append(Paragraph("Areas to improve", styles["h2"]))
        story += _bullets(quality["weaknesses"], styles)

    story.append(Paragraph("4. Automated checks on your submission", styles["h1"]))
    syntax = data["syntax"]
    if syntax["checked"]:
        outcome = "no syntax errors" if not syntax["errors"] else f"{syntax['errors']} syntax error(s)"
        story.append(Paragraph(_markup(f"Syntax: {syntax['checked']} file(s) parsed ({', '.join(syntax['languages'])}) with {outcome}."), styles["body"]))
    if data["report_sections"]:
        story.append(Paragraph(_markup("Report sections found: " + ", ".join(data["report_sections"]) + "."), styles["body"]))
    if data["screenshots_check"]:
        rows = [[Paragraph(h, styles["cellb"]) for h in ("Output screenshot", "Result", "Evidence")]]
        rows += [[Paragraph(_markup(s.get("screenshot")), styles["cell"]), Paragraph(_status(s.get("status")), styles["cell"]),
                  Paragraph(_markup(s.get("evidence"), _MAX_EVIDENCE_CHARS), styles["cell"])] for s in data["screenshots_check"]]
        story.append(_table(rows, [CONTENT_W * 0.34, CONTENT_W * 0.14, CONTENT_W * 0.52]))
    elif data["screenshot_files"]:
        story.append(Paragraph(_markup(f"Output screenshots submitted ({len(data['screenshot_files'])}): "
                                       + ", ".join(Path(f).name for f in data["screenshot_files"])), styles["body"]))
    if data["submitted_files"]:
        listed = data["submitted_files"][:_MAX_FILES_LISTED]
        more = len(data["submitted_files"]) - len(listed)
        story.append(Paragraph("Files in the submitted zip", styles["h2"]))
        story.append(Paragraph(escape(_plain(", ".join(listed) + (f"  ... and {more} more" if more > 0 else ""))), styles["mono"]))

    story.append(Paragraph("5. Viva (oral defence)", styles["h1"]))
    viva = data["viva"]
    attempts = data.get("viva_attempts", [])
    if attempts:
        story.append(Paragraph(_markup(
            f"Result: **{data.get('viva_rating', '-')}**. The viva is passed with at least {data.get('viva_pass_percent', VIVA_PASS_PERCENT)}% of the "
            f"answers correct; up to {VIVA_ATTEMPTS} attempts are allowed, each with new questions."), styles["body"]))
        rows = [[Paragraph(h, styles["cellb"]) for h in ("Attempt", "Result", "Outcome")]]
        for item in attempts:
            outcome = ('<font color="%s"><b>Passed</b></font>' % GREEN) if item["passed"] else ('<font color="%s"><b>Not passed</b></font>' % RED)
            rows.append([Paragraph(str(item["attempt"]), styles["cell"]), Paragraph(escape(item["rating"]), styles["cell"]),
                         Paragraph(outcome, styles["cell"])])
        story.append(_table(rows, [CONTENT_W * 0.2, CONTENT_W * 0.4, CONTENT_W * 0.4]))
        story.append(Paragraph("Questions and answers of the final attempt", styles["h2"]))
    else:
        story.append(Paragraph("Viva result not recorded.", styles["body"]))
    if viva:
        rows = [[Paragraph(h, styles["cellb"]) for h in ("#", "Question", "Your answer", "Result")]]
        for item in viva:
            result = ('<font color="%s"><b>Correct</b></font>' % GREEN) if item["correct"] else ('<font color="%s"><b>Not correct</b></font>' % RED)
            note = f"<br/><font size=7.5 color='#475467'>{_markup(item['note'], 160)}</font>" if item["note"] else ""
            rows.append([Paragraph(str(item["number"]), styles["cell"]), Paragraph(_markup(item["question"]), styles["cell"]),
                         Paragraph(_markup(item["answer"] or "(no answer)", _MAX_ANSWER_CHARS), styles["cell"]),
                         Paragraph(result + note, styles["cell"])])
        story.append(_table(rows, [CONTENT_W * 0.05, CONTENT_W * 0.33, CONTENT_W * 0.40, CONTENT_W * 0.22]))

    story.append(Paragraph("6. Reviewer feedback", styles["h1"]))
    story += _rich(data["feedback"], styles) or [Paragraph("No written feedback was recorded.", styles["body"])]
    if data["score_reasoning"]:
        story.append(KeepTogether([Paragraph("How the score was decided", styles["h2"]), Paragraph(_markup(data["score_reasoning"]), styles["body"])]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(_markup(
        f"This report was generated automatically from the graded submission (ID {data['report_id']}) on "
        f"{_when(data['generated_at'])}. It records the result at the time of grading."), styles["small"]))

    buffer = io.BytesIO()
    footer = f"DigiDARA Technologies  |  Capstone project report  |  {_plain(data['student_name'])}"
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=HEADER_H + 4 * mm, bottomMargin=24 * mm,
        # Page content is left uncompressed: a few KB per page, and it keeps the text inspectable in tests.
        pageCompression=0,
        title=f"Capstone Project Report - {_plain(data['project_title'])}", author="DigiDARA Technologies", subject="Capstone project completion report",
    )
    document.build(story, canvasmaker=type("NumberedCanvas", (_NumberedCanvas,), {"footer_text": footer}))
    return buffer.getvalue()
