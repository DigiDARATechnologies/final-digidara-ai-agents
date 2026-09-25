"""Render the completed interview report with readable, aligned question reviews."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    CondPageBreak, HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle, Image,
)


PURPLE = colors.HexColor("#7657F6")
INK = colors.HexColor("#24232E")
MUTED = colors.HexColor("#626575")
LINE = colors.HexColor("#DED9F2")
SOFT = colors.HexColor("#F6F3FF")
LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "digidara-logo.jpg"
LOGO_WIDTH = 38*mm
LOGO_HEIGHT = 21.375*mm


def _logo():
    return ""


def _draw_logo(canvas, doc):
    if LOGO_PATH.is_file():
        canvas.drawImage(
            ImageReader(str(LOGO_PATH)),
            A4[0] - doc.rightMargin - LOGO_WIDTH,
            A4[1] - 26*mm,
            width=LOGO_WIDTH, height=LOGO_HEIGHT,
            preserveAspectRatio=True, mask="auto",
        )


def _html(value):
    text = str(value if value is not None else "").strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return escape(text.encode("cp1252", "replace").decode("cp1252")).replace("\n", "<br/>")


def _display_choice(value):
    """Render enum-like report values in readable title case."""
    text = str(value if value is not None else "").strip()
    return text.replace("_", " ").title()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("InterviewTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=23, leading=27, textColor=INK, alignment=TA_CENTER, spaceAfter=4),
        "subtitle": ParagraphStyle("InterviewSubtitle", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=PURPLE, alignment=TA_CENTER, spaceAfter=14),
        "label": ParagraphStyle("InterviewLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=MUTED),
        "value": ParagraphStyle("InterviewValue", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=INK),
        "heading": ParagraphStyle("InterviewHeading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=PURPLE, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("InterviewBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, textColor=INK, spaceAfter=7, splitLongWords=1),
        "question_title": ParagraphStyle("InterviewQuestionTitle", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.white),
        "verdict": ParagraphStyle("InterviewVerdict", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=colors.white, alignment=TA_RIGHT),
        "field_label": ParagraphStyle("InterviewFieldLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=PURPLE, leftIndent=8*mm, spaceBefore=8, spaceAfter=3),
        "field_body": ParagraphStyle("InterviewFieldBody", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=14, textColor=INK, leftIndent=8*mm, rightIndent=3*mm, spaceAfter=2, splitLongWords=1),
    }


def _footer(canvas, doc):
    canvas.saveState()
    _draw_logo(canvas, doc)
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.5)
    canvas.line(doc.leftMargin, 13*mm, width-doc.rightMargin, 13*mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(doc.leftMargin, 8*mm, "Mock Interview Report")
    canvas.drawRightString(width-doc.rightMargin, 8*mm, f"Page {doc.page}")
    canvas.restoreState()


def _field(story, label, value, style):
    story.append(Paragraph(label, style["field_label"]))
    story.append(Paragraph(_html(value) or "Not provided", style["field_body"]))


def generate_interview_report_pdf(interview, scorecard, total_marks, max_marks):
    """Return PDF bytes; long answers can flow across pages without moving labels."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm,
        topMargin=30*mm, bottomMargin=20*mm,
        title="Mock Interview Report", author="DigiDARA",
    )
    style = _styles()
    title_block = [Paragraph("Mock Interview", style["title"]), Paragraph("Interview Report", style["subtitle"])]
    report_header = Table([[title_block, _logo()]], colWidths=[138*mm, 38*mm], hAlign="LEFT")
    report_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story = [report_header, Spacer(1, 4*mm)]

    metadata = [
        ("Student", _display_choice(interview.get("student_name"))),
        ("Role / Topic", interview.get("role_name") or interview.get("subject")),
        ("Round", _display_choice(interview.get("round_type"))),
        ("Difficulty", _display_choice(interview.get("difficulty"))),
        ("Questions", str(max_marks)),
        ("Completed", interview.get("ended_at") or interview.get("created_at")),
    ]
    detail_table = Table(
        [[Paragraph(label, style["label"]), Paragraph(_html(value) or "-", style["value"])] for label, value in metadata],
        colWidths=[39*mm, 137*mm], hAlign="LEFT",
    )
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SOFT), ("BOX", (0, 0), (-1, -1), .6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([detail_table, Paragraph("Score Summary", style["heading"])])
    scores = [
        ("Overall score", f"{interview.get('overall_score')}/10"),
        ("Knowledge", f"{interview.get('technical_accuracy')}/10"),
        ("Communication", f"{interview.get('communication_clarity')}/10"),
        ("Confidence", f"{interview.get('confidence')}/10"),
    ]
    score_table = Table(
        [[Paragraph(label, style["label"]), Paragraph(_html(value), style["value"])] for label, value in scores],
        colWidths=[55*mm, 121*mm], hAlign="LEFT",
    )
    score_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .3, LINE),
        ("BACKGROUND", (0, 0), (0, -1), SOFT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(score_table)
    for heading, key in (("Strengths", "strengths"), ("Areas to Improve", "weaknesses"), ("Feedback", "feedback")):
        story.extend([Paragraph(heading, style["heading"]), Paragraph(_html(interview.get(key)) or "Not provided", style["body"])])

    story.extend([Paragraph("Question Review", style["heading"]), HRFlowable(width="100%", thickness=1, color=PURPLE), Spacer(1, 4*mm)])
    for item in scorecard:
        story.append(CondPageBreak(90*mm))
        header = Table([[
            Paragraph(f"Question {item['question_number']}", style["question_title"]),
            Paragraph(_html(item.get("verdict") or "Unrated").title(), style["verdict"]),
        ]], colWidths=[123*mm, 53*mm], hAlign="LEFT")
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PURPLE), ("BOX", (0, 0), (-1, -1), .6, PURPLE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        question_intro = [header]
        _field(question_intro, "Question", item.get("question"), style)
        story.append(KeepTogether(question_intro))
        _field(story, "Your answer", item.get("answer"), style)
        if item.get("followup"):
            _field(story, "Follow-up question", item["followup"].get("question"), style)
            _field(story, "Follow-up answer", item["followup"].get("answer"), style)
        if item.get("verdict_reason"):
            _field(story, "Feedback", item.get("verdict_reason"), style)
        _field(story, "Recommended answer", item.get("ideal_answer"), style)
        story.extend([Spacer(1, 5*mm), HRFlowable(width="100%", thickness=.5, color=LINE), Spacer(1, 3*mm)])

    story.append(Paragraph(
        f"Correct-Answer Score: {_html(total_marks)} / {_html(max_marks)} "
        f"({len(scorecard)} questions)", style["body"]
    ))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
