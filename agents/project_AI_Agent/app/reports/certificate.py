"""The capstone project certificate (a PDF).

Issued only after BOTH the project score and the viva are passed. It is printed
on the DigiDARA certificate template (logo, seals and signature are part of that
artwork) and carries what the student actually did: their name, the project they
built, what it does, the technology and skills involved, a Good / Average / Bad
rating for the project and the viva (never a mark), the issue date and an id.

`assemble_certificate_data` turns the stored rows into a plain dict and
`build_certificate_pdf` draws it, so the layout is testable without a database.
The student can correct only their name, before confirming; the preview is the
very same PDF, rendered to an image, so what they approve is what they download.

Text is limited to what the PDF's standard fonts can draw (Latin-1 / Windows-1252).
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdf_canvas

from app.reports.final_report import _plain, _slug

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "certificate_template.png"

PAGE_W, PAGE_H = A4
TEMPLATE_W = 1414  # the template is 1414 x 2000 px; every position below is in template pixels
S = PAGE_W / TEMPLATE_W

NAVY = Color(11 / 255, 40 / 255, 78 / 255)
GOLD = Color(166 / 255, 124 / 255, 55 / 255)
GRAY = Color(70 / 255, 70 / 255, 70 / 255)
LIGHT = Color(200 / 255, 200 / 255, 200 / 255)
RATING_COLOURS = {
    "Good": Color(46 / 255, 125 / 255, 50 / 255),
    "Average": Color(183 / 255, 121 / 255, 31 / 255),
    "Bad": Color(180 / 255, 40 / 255, 40 / 255),
}

CONTENT_W = 1000        # widest text line, px
MAX_SUMMARY_CHARS = 210
_NAME_RE = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'\-]{1,59}$")

PROJECT_GOOD_SCORE = 85  # project scores at or above this are rated Good (the pass mark itself is Average)


# ------------------------------------------------------------------ data -----

def clean_recipient_name(value: Any) -> str:
    """The name to print, or a ValueError saying what is wrong with it."""
    name = " ".join(("" if value is None else str(value)).split())
    if not name:
        raise ValueError("Please enter the name to print on your certificate.")
    if len(name) < 2 or len(name) > 60:
        raise ValueError("The name must be between 2 and 60 characters.")
    if not _NAME_RE.match(name):
        raise ValueError("Use letters, spaces, dots, hyphens or apostrophes only (English/Latin letters).")
    return name


def project_rating(score: Any) -> str:
    try:
        return "Good" if float(score) >= PROJECT_GOOD_SCORE else "Average"
    except (TypeError, ValueError):
        return "Average"


def certificate_id(submission_id: str, when: datetime) -> str:
    return f"DDT-CAP-{when.year}-{str(submission_id)[:8].upper()}"


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.") + "..."


def assemble_certificate_data(assignment: Any, student: Any, submission: Any, name: str, issued_at: datetime) -> dict[str, Any]:
    """Everything printed on the certificate, from the stored rows."""
    from app.viva import viva_rating

    topic = dict(assignment.topic_json or {})
    score = dict(submission.score_json or {})
    history = list(submission.viva_attempts_json or [])
    passing = next((a for a in reversed(history) if a.get("passed")), history[-1] if history else None)
    if passing:
        viva = passing.get("rating") or viva_rating(passing.get("correct", 0), passing.get("total", 0))
    else:  # a submission that predates attempt history: rate its single stored viva
        viva = viva_rating(int(submission.viva_score or 0), len(submission.viva_questions_json or []) or 10)
    medium = topic.get("medium") or getattr(getattr(assignment, "medium", None), "value", "") or ""
    return {
        "name": name,
        "project_title": topic.get("title") or "Capstone Project",
        "summary": topic.get("summary") or topic.get("description") or "",
        "technology": str(medium).replace("_", " ").title() if str(medium).islower() else str(medium),
        "skills": [str(skill) for skill in (topic.get("skills_applied") or []) if str(skill).strip()],
        "project_rating": project_rating(score.get("final_score")),
        "viva_rating": viva,
        "issued_at": issued_at,
        "certificate_id": certificate_id(submission.id, issued_at),
    }


# ---------------------------------------------------------------- drawing ----

def _text(c: pdf_canvas.Canvas, text: str, y_px: float, font: str, size_px: float, colour: Color, x_px: float = TEMPLATE_W / 2) -> None:
    c.setFillColor(colour)
    c.setFont(font, size_px * S)
    c.drawCentredString(x_px * S, PAGE_H - y_px * S, text)


def _fit(text: str, font: str, start_px: float, min_px: float, width_px: float = CONTENT_W) -> float:
    size = start_px
    while size > min_px and stringWidth(text, font, size * S) > width_px * S:
        size -= 2
    return size


def _wrapped(c: pdf_canvas.Canvas, text: str, font: str, size_px: float, colour: Color, y_px: float, leading_px: float, max_lines: int) -> float:
    """Centred, wrapped text of at most `max_lines` lines; returns the y after it."""
    lines = simpleSplit(text, font, size_px * S, CONTENT_W * S)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,;:.") + "..."
    for line in lines:
        _text(c, line, y_px, font, size_px, colour)
        y_px += leading_px
    return y_px


def _pill(c: pdf_canvas.Canvas, label: str, rating: str, left_px: float, y_px: float, height_px: float = 46) -> float:
    text = f"{label}: {rating.upper()}"
    size = 22
    width = stringWidth(text, "Times-Bold", size * S) / S + 56
    c.setFillColor(RATING_COLOURS.get(rating, GRAY))
    c.roundRect(left_px * S, PAGE_H - (y_px + height_px) * S, width * S, height_px * S, height_px * S / 2, stroke=0, fill=1)
    c.setFillColor(Color(1, 1, 1))
    c.setFont("Times-Bold", size * S)
    c.drawCentredString((left_px + width / 2) * S, PAGE_H - (y_px + height_px / 2 + 7) * S, text)
    return width


def build_certificate_pdf(data: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4, pageCompression=0)
    title = _plain(data["project_title"], 90)
    c.setTitle(f"Certificate of Completion - {title}")
    c.setAuthor("DigiDARA Technologies Pvt Ltd")
    c.setSubject("Capstone project certificate")
    c.drawImage(ImageReader(str(TEMPLATE)), 0, 0, width=PAGE_W, height=PAGE_H)

    # Recipient: right under the pre-printed "This certificate is proudly awarded to".
    name = _plain(data["name"], 60).upper()
    _text(c, name, 830, "Times-Bold", _fit(name, "Times-Bold", 66, 34), NAVY)

    _text(c, "for successfully completing the capstone project", 950, "Times-Italic", 30, GRAY)

    project = _plain(data["project_title"], 110).upper()
    lines: list[str] = []
    for size in (46, 42, 38, 34, 30):
        lines = simpleSplit(project, "Times-Bold", size * S, CONTENT_W * S)
        if len(lines) <= 2:
            break
    if len(lines) > 2:
        lines = [lines[0], lines[1].rstrip(" ,;:.") + "..."]
    y = 1012
    for line in lines:
        _text(c, line, y, "Times-Bold", size, NAVY)
        y += size + 12

    summary = _cut(_plain(data.get("summary", "")), MAX_SUMMARY_CHARS)
    if summary:
        y = _wrapped(c, summary, "Times-Italic", 25, GRAY, y + 18, 34, 2)

    skills = [_plain(skill, 40) for skill in data.get("skills", [])][:4]
    technology = _plain(data.get("technology", ""), 30)
    while True:
        line = "  |  ".join(part for part in (f"Technology: {technology}" if technology else "", f"Skills: {', '.join(skills)}" if skills else "") if part)
        if not skills or stringWidth(line, "Times-Bold", 22 * S) <= CONTENT_W * S:
            break
        skills.pop()
    if line:
        _text(c, line, y + 26, "Times-Bold", 22, GOLD)

    # Ratings, side by side and centred -- words, never marks.
    pill_y = 1262
    project_label, viva_label = "PROJECT", "VIVA VOCE"
    widths = [
        stringWidth(f"{label}: {data[key].upper()}", "Times-Bold", 22 * S) / S + 56
        for label, key in ((project_label, "project_rating"), (viva_label, "viva_rating"))
    ]
    gap = 28
    left = (TEMPLATE_W - (sum(widths) + gap)) / 2
    left += _pill(c, project_label, data["project_rating"], left, pill_y) + gap
    _pill(c, viva_label, data["viva_rating"], left, pill_y)

    # Dotted divider, date and id -- all clear of the medal that starts at y = 1435.
    c.setFillColor(LIGHT)
    for x in range(int(TEMPLATE_W / 2 - 380), int(TEMPLATE_W / 2 + 380), 10):
        c.rect(x * S, PAGE_H - 1338 * S, 4 * S, 2 * S, stroke=0, fill=1)
    issued = data["issued_at"].strftime("%d %B %Y").lstrip("0")
    _text(c, f"Date of Issue:  {issued}", 1372, "Times-Bold", 24, GOLD)
    _text(c, f"Certificate ID:  {data['certificate_id']}", 1408, "Times-Bold", 21, GOLD)

    c.showPage()
    c.save()
    return buffer.getvalue()


def render_preview_jpeg(pdf: bytes, width_px: int = 760) -> bytes:
    """The certificate's first page as a JPEG -- the preview the student approves."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        page = document[0]
        image = page.render(scale=width_px / page.get_width()).to_pil().convert("RGB")
    finally:
        document.close()
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def certificate_filename(project_title: str, name: str) -> str:
    return f"Certificate_{_slug(_plain(name))}_{_slug(_plain(project_title))}.pdf"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
