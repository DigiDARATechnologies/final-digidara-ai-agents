"""Generate learner-facing Writing Practice Assessment PDFs."""

import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

TEAL = colors.HexColor("#0E90B4")
INK = colors.HexColor("#1A202C")
MUTED = colors.HexColor("#5A6A80")
LINE = colors.HexColor("#E2E8F0")
SOFT = colors.HexColor("#F7FAFC")
GREEN = colors.HexColor("#167A50")
ACCENT = colors.HexColor("#4A37D0")
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "digidara-logo.jpg"
LOGO_WIDTH = 34 * mm
LOGO_HEIGHT = 19 * mm


def _plain(value):
    """Return safe WinAnsi text for built-in ReportLab Helvetica."""
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u2022": "*", "\u2192": "->", "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return escape(text.encode("latin-1", "replace").decode("latin-1")).replace("\n", "<br/>")


def _draw_logo_and_footer(canvas, doc):
    canvas.saveState()
    if LOGO_PATH.is_file():
        try:
            canvas.drawImage(
                ImageReader(str(LOGO_PATH)),
                A4[0] - doc.rightMargin - LOGO_WIDTH,
                A4[1] - 22 * mm,
                width=LOGO_WIDTH,
                height=LOGO_HEIGHT,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    footer_text = "DigiDARA AI Agents Platform  |  Communication Coach Writing Practice Report"
    canvas.drawString(doc.leftMargin, 12 * mm, footer_text)
    canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def generate_writing_report_pdf(session, learner_name="Learner"):
    """Compile a professional, beautiful PDF report for a completed writing session."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
    )

    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=INK,
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=TEAL,
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    section_h1 = ParagraphStyle(
        "SectionH1",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=INK,
    )
    muted_body = ParagraphStyle(
        "MutedBody",
        parent=body_style,
        textColor=MUTED,
        fontSize=8.5,
        leading=12,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    score_big = ParagraphStyle(
        "ScoreBig",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=TEAL,
    )
    score_label = ParagraphStyle(
        "ScoreLabel",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=MUTED,
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("Writing Practice Report", title_style))
    story.append(Paragraph("AI Communication Coach Performance Assessment", subtitle_style))
    story.append(Spacer(1, 4))

    # Metadata Card Table
    created_date = session.created_at.strftime("%d %B %Y, %I:%M %p") if getattr(session, "created_at", None) else "Recent"
    mode_label = (session.mode or "Topic Practice").replace("_", " ").title()
    difficulty_label = (session.difficulty or "Medium").title()
    topic_label = session.topic_title or "General Conversation"

    meta_data = [
        [
            Paragraph(f"<b>Student:</b> {_plain(learner_name)}", body_style),
            Paragraph(f"<b>Date:</b> {_plain(created_date)}", body_style),
        ],
        [
            Paragraph(f"<b>Topic:</b> {_plain(topic_label)}", body_style),
            Paragraph(f"<b>Mode:</b> {_plain(mode_label)} ({_plain(difficulty_label)})", body_style),
        ],
        [
            Paragraph(f"<b>Submitted Responses:</b> {len([t for t in session.turns if getattr(t, 'user_response', None) or getattr(t, 'user_answer', None)])}", body_style),
            Paragraph(f"<b>Status:</b> Completed", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[90 * mm, 88 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Overall Scorecard Banner
    overall_val = round(float(session.overall_score), 1) if session.overall_score is not None else 8.0
    grammar_val = round(float(session.grammar_score), 1) if getattr(session, "grammar_score", None) is not None else overall_val
    vocab_val = round(float(session.vocabulary_score), 1) if getattr(session, "vocabulary_score", None) is not None else overall_val
    clarity_val = round(float(session.clarity_score), 1) if getattr(session, "clarity_score", None) is not None else overall_val

    score_data = [
        [
            Paragraph(f"{overall_val} <font size=10>/ 10</font>", score_big),
            Paragraph(f"{grammar_val} <font size=10>/ 10</font>", score_big),
            Paragraph(f"{vocab_val} <font size=10>/ 10</font>", score_big),
            Paragraph(f"{clarity_val} <font size=10>/ 10</font>", score_big),
        ],
        [
            Paragraph("OVERALL SCORE", score_label),
            Paragraph("GRAMMAR", score_label),
            Paragraph("VOCABULARY", score_label),
            Paragraph("CLARITY & STRUCTURE", score_label),
        ],
    ]
    score_table = Table(score_data, colWidths=[44.5 * mm] * 4)
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#BBF7D0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCFCE7")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 10))

    # Executive Summary
    summary_text = getattr(session, "summary_feedback", None) or "You completed the speaking practice session. You expressed your ideas clearly and kept the conversation moving."
    story.append(Paragraph("Coach Evaluation Summary", section_h1))
    story.append(Paragraph(_plain(summary_text), body_style))
    story.append(Spacer(1, 8))

    # Strengths & Areas to Improve
    strengths = []
    if getattr(session, "strengths_json", None):
        try:
            strengths = json.loads(session.strengths_json)
        except Exception:
            pass
    if not strengths:
        strengths = ["Engaged enthusiastically with the topic.", "Used clear vocabulary to communicate thoughts."]

    improvements = []
    if getattr(session, "weaknesses_json", None):
        try:
            improvements = json.loads(session.weaknesses_json)
        except Exception:
            pass
    if not improvements:
        improvements = ["Add specific examples when answering questions.", "Practice full sentence structures for smoother flow."]

    perf_cols = [
        [
            Paragraph("<b>Key Strengths</b>", ParagraphStyle("H", parent=body_style, textColor=GREEN, fontName="Helvetica-Bold")),
            Spacer(1, 3),
        ] + [Paragraph(f"* {_plain(s)}", bullet_style) for s in strengths],
        [
            Paragraph("<b>Areas for Growth</b>", ParagraphStyle("H", parent=body_style, textColor=ACCENT, fontName="Helvetica-Bold")),
            Spacer(1, 3),
        ] + [Paragraph(f"* {_plain(i)}", bullet_style) for i in improvements],
    ]
    perf_table = Table([[perf_cols[0], perf_cols[1]]], colWidths=[89 * mm, 89 * mm])
    perf_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F0FDF4")),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F5F3FF")),
        ("BOX", (0, 0), (0, 0), 0.8, colors.HexColor("#DCFCE7")),
        ("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#DDD6FE")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(perf_table)
    story.append(Spacer(1, 10))

    # Turn-by-Turn Question & Feedback Review
    story.append(Paragraph("Writing Submission Review & Corrections", section_h1))
    
    answered_turns = [t for t in session.turns if getattr(t, "user_response", None) or getattr(t, "user_answer", None)]
    if not answered_turns:
        story.append(Paragraph("No written responses were submitted in this session.", muted_body))
    else:
        for idx, turn in enumerate(answered_turns, start=1):
            prompt = getattr(turn, "ai_prompt", None) or getattr(turn, "ai_question", "Writing Prompt")
            answer = getattr(turn, "user_response", None) or getattr(turn, "user_answer", "")
            feedback_text = getattr(turn, "feedback", "") or getattr(turn, "reaction", "") or ""
            correction = getattr(turn, "corrected_answer", None)
            better = getattr(turn, "better_natural_answer", None)
            
            turn_elements = [
                Paragraph(f"<b>Turn {idx} - Prompt:</b> {_plain(prompt)}", body_style),
                Spacer(1, 2),
                Paragraph(f"<b>Your Written Response:</b> <i>\"{_plain(answer)}\"</i>", ParagraphStyle("Ans", parent=body_style, textColor=colors.HexColor("#2B6CB0"))),
            ]
            if feedback_text:
                turn_elements.append(Spacer(1, 2))
                turn_elements.append(Paragraph(f"<b>AI Feedback:</b> {_plain(feedback_text)}", muted_body))
            if correction and str(correction).strip() != str(answer).strip():
                turn_elements.append(Spacer(1, 2))
                turn_elements.append(Paragraph(f"<b>Grammar & Correction:</b> <font color='#167A50'>{_plain(correction)}</font>", body_style))
            if better and str(better).strip() != str(answer).strip() and str(better).strip() != str(correction).strip():
                turn_elements.append(Spacer(1, 2))
                turn_elements.append(Paragraph(f"<b>Natural Polish:</b> <font color='#4A37D0'>{_plain(better)}</font>", body_style))
            
            turn_box = Table([[turn_elements]], colWidths=[178 * mm])
            turn_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(KeepTogether([turn_box, Spacer(1, 6)]))

    # Build Document with Header and Footer
    doc.build(story, onFirstPage=_draw_logo_and_footer, onLaterPages=_draw_logo_and_footer)
    return buffer.getvalue()
