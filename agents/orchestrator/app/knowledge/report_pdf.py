"""A knowledge test report as a PDF, headed by the DigiDARA AI Agents logo."""
from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.billing.invoice import LOGO
from app.billing.invoice import _logo as invoice_logo

VERDICT = {"correct": "Correct", "partial": "Partly correct", "wrong": "Incorrect", "ungraded": "Not graded"}
VERDICT_COLOR = {"correct": "#15803d", "partial": "#b45309", "wrong": "#b91c1c", "ungraded": "#475569"}


def _p(text: object, style) -> Paragraph:
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def _when(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return value


def build(report: dict) -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, textColor=colors.HexColor("#475569"))
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=17, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=f"{report.get('title', 'Test')} report")
    story: list = []
    if LOGO.exists():
        story += [invoice_logo(), Spacer(1, 6)]
    story.append(_p(report.get("title", "Knowledge test"), h1))
    story.append(_p(" · ".join(x for x in (report.get("organization"), report.get("learner"), report.get("email"),
                                            _when(report.get("finished_at"))) if x), small))
    story.append(Spacer(1, 8))
    facts = [["Score", "Percentage", "Integrity"],
             [f"{report.get('score', 0)} / {report.get('max', 0)}", f"{report.get('percent', 0)}%",
              "-" if report.get("integrity") is None else f"{report['integrity']} / 100"]]
    table = Table(facts, colWidths=[58 * mm] * 3)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTSIZE", (0, 1), (-1, 1), 14), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    if report.get("summary"):
        story += [_p("Summary", h2), _p(report["summary"], body)]
    for label, key in (("Strengths", "strengths"), ("To revise", "improve")):
        if report.get(key):
            story += [_p(label, h2)] + [_p(f"• {item}", body) for item in report[key]]
    story.append(_p("Question by question", h2))
    for row in report.get("rows", []):
        verdict = row.get("verdict", "ungraded")
        color = VERDICT_COLOR.get(verdict, "#475569")
        story.append(Paragraph(
            f"<b>Q{row.get('number')}.</b> {escape(str(row.get('question', '')))} "
            f"<font color='{color}'><b>[{VERDICT.get(verdict, verdict)}, {row.get('points', 0)} pt]</b></font>", body))
        if row.get("qtype") == "mcq":
            letters = "ABCD"
            options = "   ".join(f"{letters[i]}. {opt}" for i, opt in enumerate(row.get("options", [])[:4]))
            story.append(_p(options, small))
        your = row.get("your_answer") or ("(no answer - time ran out)" if row.get("timed_out") else "(no answer)")
        story.append(_p(f"Your answer: {your}", body))
        if verdict != "correct":
            story.append(_p(f"Correct answer: {row.get('correct_answer', '')}", body))
        if row.get("feedback"):
            story.append(_p(f"Feedback: {row['feedback']}", small))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buffer.getvalue()
