"""Generate learner-facing assessment PDFs without persisting files."""

from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
    TableStyle, Image,
)

from .test_label import test_label
from ..utils.code_formatting import FENCE_PATTERN, LIKELY_CODE_PATTERN, decode_literal_layout
from ..utils.timezone import format_local_datetime, valid_timezone
from ..topic_config import topic_is_starred


PURPLE=colors.HexColor("#7657F6")
CYAN=colors.HexColor("#35C9E9")
INK=colors.HexColor("#24232E")
MUTED=colors.HexColor("#626575")
LINE=colors.HexColor("#DED9F2")
SOFT=colors.HexColor("#F6F3FF")
GREEN=colors.HexColor("#167A50")
ROSE=colors.HexColor("#A43B49")
LOGO_PATH=Path(__file__).resolve().parents[2]/"assets"/"digidara-logo.jpg"
LOGO_WIDTH=38*mm
LOGO_HEIGHT=21.375*mm


def _logo():
    return ""


def _draw_logo(canvas,doc):
    if LOGO_PATH.is_file():
        canvas.drawImage(
            ImageReader(str(LOGO_PATH)),
            A4[0]-doc.rightMargin-LOGO_WIDTH,
            A4[1]-26*mm,
            width=LOGO_WIDTH,height=LOGO_HEIGHT,
            preserveAspectRatio=True,mask="auto",
        )


def _plain(value):
    """Return safe WinAnsi-friendly text for ReportLab's built-in fonts."""
    if value is None:
        return ""
    text=str(value)
    replacements={
        "\u2011":"-","\u2012":"-","\u2013":"-","\u2014":"-",
        "\u2018":"'","\u2019":"'","\u201c":"\"","\u201d":"\"",
        "\u2026":"...","\u00d7":" x ","\u00f7":" / ","\u2264":" <= ",
        "\u2265":" >= ","\u2260":" != ","\u2192":" -> ","\u00b7":" - ",
    }
    for source,target in replacements.items():
        text=text.replace(source,target)
    return text.encode("cp1252","replace").decode("cp1252")


def _html(value):
    return escape(_plain(decode_literal_layout(value))).replace("\n","<br/>")


def _content_flowables(value,prose_style,code_style,technical=False):
    """Render learner text as paragraphs plus indented monospace code."""
    normalized=decode_literal_layout(value).strip()
    if not technical:
        return [Paragraph(_html(normalized),prose_style)]
    matches=list(FENCE_PATTERN.finditer(normalized))
    segments=[]
    cursor=0
    for match in matches:
        prose=normalized[cursor:match.start()].strip()
        if prose:segments.append(("prose",prose))
        segments.append(("code",match.group("code").strip("\n")))
        cursor=match.end()
    tail=normalized[cursor:].strip()
    if tail:segments.append(("prose",tail))
    if not matches and "\n" in normalized:
        lines=normalized.split("\n")
        first_code=next((index for index,line in enumerate(lines) if LIKELY_CODE_PATTERN.search(line)),None)
        if first_code is not None:
            tail_start=next((
                index for index in range(first_code+1,len(lines))
                if not lines[index-1].strip() and re.match(r"\s*(?:what|which|how|why|identify|determine|select|choose)\b",lines[index],re.IGNORECASE)
            ),len(lines))
            segments=[]
            prose="\n".join(lines[:first_code]).strip()
            code="\n".join(lines[first_code:tail_start]).strip("\n")
            trailing="\n".join(lines[tail_start:]).strip()
            if prose:segments.append(("prose",prose))
            if code:segments.append(("code",code))
            if trailing:segments.append(("prose",trailing))
    if not segments:
        segments=[("prose",normalized)]
    return [
        Preformatted(_plain(content),code_style) if kind=="code" else Paragraph(_html(content),prose_style)
        for kind,content in segments
    ]


def _completed_at(test, fallback_timezone=None):
    value=test.completed_at
    if not value:
        return ""
    timezone_name=valid_timezone(getattr(test,"timezone",None)) or valid_timezone(fallback_timezone)
    return format_local_datetime(value,timezone_name)


def _styles():
    base=getSampleStyleSheet()
    return {
        "title":ParagraphStyle(
            "PdfTitle",parent=base["Title"],fontName="Helvetica-Bold",
            fontSize=23,leading=27,textColor=INK,alignment=TA_CENTER,spaceAfter=4,
        ),
        "subtitle":ParagraphStyle(
            "PdfSubtitle",parent=base["Normal"],fontName="Helvetica-Bold",
            fontSize=10,leading=14,textColor=PURPLE,alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "label":ParagraphStyle(
            "PdfLabel",parent=base["Normal"],fontName="Helvetica-Bold",
            fontSize=8,leading=10,textColor=MUTED,spaceAfter=2,
        ),
        "value":ParagraphStyle(
            "PdfValue",parent=base["Normal"],fontName="Helvetica-Bold",
            fontSize=11,leading=14,textColor=INK,
        ),
        "question_title":ParagraphStyle(
            "QuestionTitle",parent=base["Heading2"],fontName="Helvetica-Bold",
            fontSize=13,leading=17,textColor=INK,spaceAfter=5,
        ),
        "meta":ParagraphStyle(
            "QuestionMeta",parent=base["Normal"],fontName="Helvetica-Bold",
            fontSize=8.5,leading=11,textColor=PURPLE,spaceAfter=8,
        ),
        "body":ParagraphStyle(
            "PdfBody",parent=base["BodyText"],fontName="Helvetica",
            fontSize=9.5,leading=14,textColor=INK,spaceAfter=7,
        ),
        "option":ParagraphStyle(
            "PdfOption",parent=base["BodyText"],fontName="Helvetica",
            fontSize=9,leading=12,textColor=INK,
        ),
        "answer":ParagraphStyle(
            "PdfAnswer",parent=base["BodyText"],fontName="Helvetica-Bold",
            fontSize=9,leading=13,textColor=INK,
        ),
        "explanation":ParagraphStyle(
            "PdfExplanation",parent=base["BodyText"],fontName="Helvetica",
            fontSize=9,leading=14,textColor=colors.HexColor("#353249"),
        ),
        "code":ParagraphStyle(
            "PdfCode",parent=base["Code"],fontName="Courier",
            fontSize=7.8,leading=10,textColor=INK,leftIndent=5,rightIndent=5,
            spaceBefore=3,spaceAfter=5,backColor=colors.HexColor("#F1F2F6"),
            borderColor=LINE,borderWidth=.5,borderPadding=6,
        ),
    }


def _page_footer(canvas,doc):
    canvas.saveState()
    _draw_logo(canvas,doc)
    width,_height=A4
    canvas.setStrokeColor(LINE);canvas.setLineWidth(.5)
    canvas.line(doc.leftMargin,13*mm,width-doc.rightMargin,13*mm)
    canvas.setFillColor(MUTED);canvas.setFont("Helvetica",8)
    canvas.drawString(doc.leftMargin,8*mm,"Aptitude Test Result")
    canvas.drawRightString(width-doc.rightMargin,8*mm,f"Page {doc.page}")
    canvas.restoreState()


def generate_test_results_pdf(test,student,fallback_timezone=None):
    """Return a complete assessment report as PDF bytes."""
    output=BytesIO()
    document=SimpleDocTemplate(
        output,pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,
        topMargin=30*mm,bottomMargin=20*mm,
        title=f"Aptitude Test - {test_label(test)} results",author="Aptitude Test",
    )
    style=_styles();story=[]
    title_block=[
        Paragraph("APTITUDE TEST",style["title"]),
        Paragraph("Assessment Results",style["subtitle"]),
        Paragraph(_html(test_label(test)),style["subtitle"]),
    ]
    report_header=Table([[title_block,_logo()]],colWidths=[138*mm,38*mm],hAlign="LEFT")
    report_header.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    story.extend([report_header,Spacer(1,4*mm)])
    test_type="Category Practice" if test.test_mode=="category_practice" else "Mixed Test"
    details=[
        [Paragraph("STUDENT",style["label"]),Paragraph("TEST TYPE",style["label"]),Paragraph("COMPLETED",style["label"])],
        [Paragraph(_html(student.name),style["value"]),Paragraph(_html(test_type),style["value"]),Paragraph(_html(_completed_at(test,fallback_timezone)),style["value"])],
    ]
    detail_table=Table(details,colWidths=[55*mm,46*mm,58*mm],hAlign="CENTER")
    detail_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),SOFT),("BOX",(0,0),(-1,-1),.7,LINE),
        ("INNERGRID",(0,0),(-1,-1),.4,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
        ("TOPPADDING",(0,0),(-1,0),8),("BOTTOMPADDING",(0,0),(-1,0),2),
        ("TOPPADDING",(0,1),(-1,1),2),("BOTTOMPADDING",(0,1),(-1,1),9),
    ]))
    story.extend([detail_table,Spacer(1,7*mm)])

    category=test.selected_category if test.test_mode=="category_practice" else "All configured categories"
    difficulty=test.selected_level if test.test_mode=="category_practice" else "Easy, Medium & Hard"
    summary=[
        ["SCORE",f"{test.score} / {test.total_questions}"],
        ["PERCENTAGE",f"{float(test.percentage):g}%"],
        ["CATEGORY",category or "Category Practice"],
        ["DIFFICULTY",difficulty or "Fixed"],
    ]
    if test.technical_language:
        summary.append(["TECHNICAL LANGUAGE",test.technical_language])
    summary_table=Table(
        [[Paragraph(_html(label),style["label"]),Paragraph(_html(value),style["value"])] for label,value in summary],
        colWidths=[42*mm,117*mm],hAlign="CENTER",
    )
    summary_table.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.7,LINE),("INNERGRID",(0,0),(-1,-1),.4,LINE),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F3F0FF")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),9),
        ("RIGHTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    story.extend([summary_table,Spacer(1,5*mm),Paragraph("Priority Topics to Improve",style["question_title"]),HRFlowable(width="100%",thickness=1,color=PURPLE),Spacer(1,3*mm)])
    priority_topics=[]
    seen_topics=set()
    for question in test.questions:
        category=str(question.category or "").strip()
        topic=str(question.topic or "").strip()
        key=(category.casefold(),topic.casefold())
        if category and topic and key not in seen_topics and topic_is_starred(category,topic):
            priority_topics.append((category,topic));seen_topics.add(key)
    if priority_topics:
        for category,topic in priority_topics:
            story.append(Paragraph(
                f"<font color='#7657F6'><b>PRIORITY</b></font> &nbsp; {_html(category)} - {_html(topic)}",
                style["body"],
            ))
    else:
        story.append(Paragraph("No priority topics identified for this assessment.",style["body"]))
    story.extend([Spacer(1,4*mm),Paragraph("Question Review",style["question_title"]),HRFlowable(width="100%",thickness=1,color=PURPLE),Spacer(1,4*mm)])

    for question in test.questions:
        answer=question.answer
        selected=answer.selected_answer if answer else None
        correct=question.correct_answer
        state="Correct" if answer and answer.is_correct else "Timed out" if answer and answer.timed_out else "Incorrect" if answer else "Not answered"
        option_rows=[]
        for key,value in question.options.items():
            markers=[]
            if key==correct:markers.append("Correct")
            if key==selected:markers.append("Selected")
            suffix=f" ({', '.join(markers)})" if markers else ""
            option_rows.append([Paragraph(f"<b>{key}.</b>",style["option"]),_content_flowables(f"{value}{suffix}",style["option"],style["code"],question.category=="Technical Aptitude")])
        option_table=Table(option_rows,colWidths=[9*mm,146*mm],hAlign="LEFT")
        option_table.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"TOP"),("BOX",(0,0),(-1,-1),.4,LINE),
            ("INNERGRID",(0,0),(-1,-1),.3,LINE),("LEFTPADDING",(0,0),(-1,-1),6),
            ("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),
            ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        block=[
            Paragraph(f"Question {question.sequence_no}: {_html(question.topic or 'Aptitude question')}",style["question_title"]),
            Paragraph(f"{_html(question.category)} | {_html(question.difficulty)} | <font color='{'#167A50' if state=='Correct' else '#A43B49'}'>{state}</font>",style["meta"]),
            *_content_flowables(question.question_text,style["body"],style["code"],question.category=="Technical Aptitude"),option_table,Spacer(1,3*mm),
            Paragraph(f"Your answer: <b>{_html(selected or 'Not answered')}</b> &nbsp;&nbsp; Correct answer: <b>{_html(correct)}</b>",style["answer"]),
        ]
        if question.explanation:
            block.extend([
                Spacer(1,2*mm),
                Paragraph("<b>Explanation</b>",style["answer"]),
                *_content_flowables(question.explanation,style["explanation"],style["code"],question.category=="Technical Aptitude"),
            ])
        story.extend([KeepTogether(block),Spacer(1,5*mm),HRFlowable(width="100%",thickness=.5,color=LINE),Spacer(1,5*mm)])

    document.build(story,onFirstPage=_page_footer,onLaterPages=_page_footer)
    return output.getvalue()
