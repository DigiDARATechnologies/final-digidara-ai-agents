"""Downloadable PDF report of a finished exam attempt: every question, the
learner's answer, the correct answer and whether it was right.

Available for passed AND failed attempts, for both the conversational chat
exam and the form exam. Built in memory from what is already stored; nothing
about how exams run is changed.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from cert_app.config import get_settings
from cert_app.db import chat_repository
from cert_app.db.database import get_connection

settings = get_settings()

_FINISHED_CHAT_STATUSES = {"completed", "failed"}
_FINISHED_EXAM_STATUSES = {"passed", "failed"}

_GREEN = colors.HexColor("#1b7f3b")
_RED = colors.HexColor("#b42318")
_GREY = colors.HexColor("#667085")
_LIGHT = colors.HexColor("#f2f4f7")
_ORANGE = colors.HexColor("#e8590c")


# ─── Data collection ──────────────────────────────────────────────────────────

def _user_name(user_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return (row or {}).get("name") or "Learner"
    finally:
        cursor.close()
        conn.close()


def _rows_from_form_exam(user_id: int, exam_id: int) -> Tuple[Dict, List[Dict]]:
    from cert_app.services.exam_service import get_exam_detail

    exam = get_exam_detail(user_id, exam_id)  # raises ValueError if not the learner's
    if exam.get("status") not in _FINISHED_EXAM_STATUSES:
        raise ValueError("The exam report is available once the exam is finished.")
    rows = []
    for q in exam.get("questions", []):
        options = q.get("options") or []
        answered = q.get("user_answer")
        rows.append({
            "question": q.get("question_text", ""),
            "options": options,
            "user_answer": answered if answered else None,
            "correct_answer": q.get("correct_answer") or "",
            "explanation": "" if options else (q.get("ai_feedback") or ""),
            "is_correct": None if q.get("score") is None else bool(q.get("score")),
        })
    summary = {
        "topic": exam.get("topic", ""),
        "score": exam.get("score_percentage") or 0.0,
        "passed": exam.get("status") == "passed",
        "date": exam.get("completed_at") or exam.get("started_at"),
        "closed_reason": None,
    }
    return summary, rows


def _rows_from_chat_session(session: Dict) -> List[Dict]:
    """Pair every exam question in the chat history with the learner's answer
    and the grading feedback that followed it."""
    bank = chat_repository.get_session_questions(session["id"])
    history = chat_repository.get_message_history(session["id"])

    answers: Dict[int, Dict] = {}
    current: Optional[int] = None
    for msg in history:
        meta = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
        if msg.get("role") == "assistant" and meta.get("phase") == "exam" and "question_index" in meta:
            current = int(meta["question_index"])
        elif msg.get("role") == "user" and current is not None and current not in answers:
            text = (msg.get("content") or "").strip()
            if text.startswith("force_"):
                continue
            answers[current] = {"answer": text}
        elif msg.get("role") == "assistant" and meta.get("phase") == "exam" and "score_delta" in meta \
                and current is not None and current in answers and "score" not in answers[current]:
            answers[current]["score"] = int(meta["score_delta"])
            answers[current]["feedback"] = msg.get("content") or ""

    rows = []
    for idx, q in enumerate(bank):
        options = q.get("options") or []
        given = answers.get(idx, {})
        answer = given.get("answer")
        if answer and answer.lower() == "timeout":
            answer = "No answer (time ran out)"
        rows.append({
            "question": q.get("question", ""),
            "options": options,
            "user_answer": answer,
            "correct_answer": q.get("correct_answer") if options else q.get("expected_answer", ""),
            "explanation": q.get("expected_answer", "") if options else given.get("feedback", ""),
            "is_correct": None if "score" not in given else bool(given["score"]),
        })
    return rows


def _chat_closed_reason(session_id: str) -> Optional[str]:
    for msg in reversed(chat_repository.get_message_history(session_id)):
        meta = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
        if msg.get("message_type") == "certificate_card":
            return "Exam closed after three tab switches." if meta.get("reason") == "tab_switch_limit" else None
    return None


# ─── PDF rendering ────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=18, textColor=_ORANGE, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=_GREY, alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9, leading=12),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=8, leading=10, textColor=_GREY),
        "code": ParagraphStyle("c", parent=base["Normal"], fontName="Courier", fontSize=8, leading=10,
                               backColor=_LIGHT, borderPadding=3, leftIndent=4, spaceBefore=2, spaceAfter=2),
    }


def _hex(color) -> str:
    return "#" + color.hexval()[2:]


def _plain(text) -> str:
    """Escape for a reportlab Paragraph, drop Markdown markers, keep line breaks."""
    text = str(text or "").replace("**", "").replace("`", "")
    return escape(text).replace("\n", "<br/>")


def _question_flowables(text: str, st) -> List:
    """Question text with any fenced code block shown in a monospace box."""
    parts = re.split(r"```[^\n]*\n?(.*?)```", str(text or ""), flags=re.DOTALL)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            code = escape(part.rstrip("\n")).replace(" ", "&nbsp;").replace("\n", "<br/>")
            out.append(Paragraph(code, st["code"]))
        elif part.strip():
            out.append(Paragraph(_plain(part.strip()), st["body"]))
    return out or [Paragraph("", st["body"])]


def _format_date(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    if value:
        try:
            return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
        except ValueError:
            return str(value)[:10]
    return datetime.now().strftime("%d %b %Y")


def _render_pdf(learner: str, summary: Dict, rows: List[Dict]) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{summary['topic']} exam report", author="CertifyAI")

    total = len(rows)
    correct = sum(1 for r in rows if r["is_correct"])
    incorrect = sum(1 for r in rows if r["is_correct"] is False)
    unanswered = total - correct - incorrect
    passed = summary["passed"]

    story: List = [
        Paragraph("Certification Exam Report", st["title"]),
        Paragraph("CertifyAI · DigiDARA", st["sub"]),
        Spacer(1, 8),
    ]

    outcome = f'<font color="{_hex(_GREEN if passed else _RED)}"><b>{"PASSED" if passed else "FAILED"}</b></font>'
    info = [
        ["Learner", learner, "Date", _format_date(summary.get("date"))],
        ["Topic", summary["topic"] or "—", "Result", Paragraph(outcome, st["body"])],
        ["Score", f"{round(float(summary['score'] or 0), 2)}%", "Pass mark", f"{settings.PASS_SCORE:g}%"],
        ["Correct", f"{correct} of {total}", "Incorrect / not answered", f"{incorrect} / {unanswered}"],
    ]
    info_table = Table(info, colWidths=[24 * mm, 64 * mm, 40 * mm, 50 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), _GREY),
        ("TEXTCOLOR", (2, 0), (2, -1), _GREY),
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    if summary.get("closed_reason"):
        story += [Spacer(1, 4), Paragraph(_plain(summary["closed_reason"]), st["small"])]

    wrong = [i for i, r in enumerate(rows, 1) if not r["is_correct"]]
    story.append(Paragraph("Summary", st["h2"]))
    if not wrong:
        story.append(Paragraph("Every question was answered correctly. Excellent work!", st["body"]))
    else:
        story.append(Paragraph(
            f"Review these questions before your next attempt: <b>{', '.join(f'Q{i}' for i in wrong)}</b>.",
            st["body"],
        ))

    story.append(Paragraph("Question-by-question review", st["h2"]))
    for i, r in enumerate(rows, 1):
        if r["is_correct"]:
            badge, color = "CORRECT", _GREEN
        elif r["is_correct"] is False:
            badge, color = "INCORRECT", _RED
        else:
            badge, color = "NOT ANSWERED", _GREY
        header = Paragraph(
            f'<b>Q{i}.</b> <font color="{_hex(color)}"><b>{badge}</b></font>', st["body"]
        )
        block = [header] + _question_flowables(r["question"], st)
        your = r["user_answer"] if r["user_answer"] else "Not answered"
        detail = [
            [Paragraph("<b>Your answer</b>", st["small"]), Paragraph(_plain(your), st["body"])],
            [Paragraph("<b>Correct answer</b>", st["small"]), Paragraph(_plain(r["correct_answer"] or "—"), st["body"])],
        ]
        if r.get("explanation"):
            detail.append([Paragraph("<b>Explanation</b>", st["small"]), Paragraph(_plain(r["explanation"]), st["small"])])
        table = Table(detail, colWidths=[30 * mm, 148 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBEFORE", (0, 0), (0, -1), 2, color),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        block += [Spacer(1, 2), table, Spacer(1, 8)]
        story.append(KeepTogether(block))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_GREY)
        canvas.drawString(16 * mm, 8 * mm, f"{learner} · {summary['topic']} · generated {datetime.now():%d %b %Y}")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _filename(topic: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", topic or "exam").strip("_")[:60] or "exam"
    return f"exam_report_{slug}.pdf"


# ─── Public API ───────────────────────────────────────────────────────────────

def build_chat_exam_report(session_id: str, user_id: int) -> Tuple[bytes, str]:
    """Report for a finished chat-exam session owned by `user_id`."""
    session = chat_repository.get_session(session_id)
    if not session or int(session["user_id"]) != int(user_id):
        raise LookupError("Exam session not found")
    if session.get("status") not in _FINISHED_CHAT_STATUSES:
        raise ValueError("The exam report is available once the exam is finished.")

    # A chat session launched as the form exam keeps its answers in the exam tables.
    if session.get("exam_id"):
        try:
            summary, rows = _rows_from_form_exam(user_id, int(session["exam_id"]))
            if any(r["user_answer"] for r in rows):
                return _render_pdf(_user_name(user_id), summary, rows), _filename(summary["topic"])
        except ValueError:
            pass

    rows = _rows_from_chat_session(session)
    if not rows:
        raise ValueError("No questions were recorded for this exam.")
    summary = {
        "topic": session.get("topic", ""),
        "score": session.get("score") or 0.0,
        "passed": session.get("status") == "completed",
        "date": session.get("completed_at") or session.get("started_at"),
        "closed_reason": _chat_closed_reason(session_id),
    }
    return _render_pdf(_user_name(user_id), summary, rows), _filename(summary["topic"])


def build_form_exam_report(exam_id: int, user_id: int) -> Tuple[bytes, str]:
    """Report for a finished form exam owned by `user_id`."""
    try:
        summary, rows = _rows_from_form_exam(user_id, exam_id)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise LookupError("Exam not found") from exc
        raise
    return _render_pdf(_user_name(user_id), summary, rows), _filename(summary["topic"])
