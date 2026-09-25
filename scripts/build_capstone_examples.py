"""Build the Capstone agent's downloadable example files, once.

Produces, under public/capstone-examples/ (served as static files by the
frontend, so nothing is generated at request time):

    capstone-example-report.pdf      a filled-in project report (a PDF, so it is
                                     a read-only reference and can't be mistaken
                                     for the .docx the student uploads); the
                                     DigiDARA Technologies logo is on every page
    capstone-example-project.zip     the matching source-code archive

The report has only the three sections a student's .docx needs -- Problem
Statement, Approach and Conclusion. It deliberately has no code and no
screenshots: the code AND the output screenshots both live in the zip (the
screenshots in its output_screenshots folder), and the report is only for the
student's own explanation.

The zip is built from the real, runnable project in
agents/project_AI_Agent/examples/expense-tracker: the program and its tests are
actually executed here and their genuine output is rendered into the screenshots,
so the example is internally consistent. The outputs are committed and built
deterministically (fixed zip timestamps, reportlab's invariant mode), so
re-running this script only changes them when the example itself changes:

    pip install reportlab
    python scripts/build_capstone_examples.py
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Byte-identical output for identical input: fixed dates and document IDs.
rl_config.invariant = 1

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "agents/project_AI_Agent/examples/expense-tracker"
LOGO = ROOT / "scripts/assets/digidara-technologies-logo.png"
OUT_DIR = ROOT / "public/capstone-examples"
SLUG = "expense-tracker"
ZIP_NAME = "capstone-example-project.zip"
PDF_NAME = "capstone-example-report.pdf"
# Fixed timestamp so rebuilding produces a byte-identical archive.
ZIP_TIME = (2026, 9, 19, 0, 0, 0)
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv"}
SKIP_FILES = {"expenses.json"}  # runtime data written by `add`, never shipped

BRAND_BLUE = colors.HexColor("#004AAD")
INK = colors.HexColor("#101828")
MUTED = colors.HexColor("#475467")
RULE = colors.HexColor("#D0D5DD")
PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
HEADER_H = 40 * mm  # room for the logo plus a rule under it
LOGO_W = 62 * mm


FONT_CANDIDATES = ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return (result.stdout + result.stderr).rstrip("\n")


def load_font(size):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise SystemExit("No monospace font found; install DejaVu Sans Mono or run on Windows.")


def render_terminal(path, title, lines):
    """Draw a light terminal window (dark text on white: reliable for OCR)."""
    font, small = load_font(22), load_font(17)
    line_height, pad, bar = 32, 28, 44
    width = max(int(font.getlength(line)) for line in lines) + pad * 2
    width = max(width, 760)
    height = bar + pad * 2 + line_height * len(lines)
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, bar], fill="#e4e7ec")
    for index, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        draw.ellipse([16 + index * 26, 14, 30 + index * 26, 28], fill=color)
    draw.text((width // 2 - int(small.getlength(title)) // 2, 12), title, fill="#344054", font=small)
    for index, line in enumerate(lines):
        color = "#0b6b2a" if line.startswith("$ ") else "#101828"
        draw.text((pad, bar + pad + index * line_height), line, fill=color, font=font)
    draw.rectangle([0, 0, width - 1, height - 1], outline="#cbd2dc")
    image.save(path, optimize=True)


def capture(work):
    """Run the real program and its tests; return {screenshot: (title, lines)}."""
    python = sys.executable
    add_cmds = [
        ["add", "--amount", "250", "--category", "Food", "--note", "Lunch"],
        ["add", "--amount", "1499", "--category", "Bills", "--note", "Internet"],
        ["add", "--amount", "-5", "--category", "Food"],
    ]
    first = []
    for args in add_cmds:
        first += ["$ python src/main.py " + " ".join(f'"{a}"' if " " in a else a for a in args)]
        first += run([python, "src/main.py", *args], work).splitlines()
    summary = ["$ python src/main.py summary"] + run([python, "src/main.py", "summary"], work).splitlines()
    tests = run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work).splitlines()
    tests = [line for line in tests if line.strip()]
    return {
        "01-add-expense.png": ("Terminal - adding expenses", first),
        "02-category-summary.png": ("Terminal - category summary", summary),
        "03-tests-passing.png": ("Terminal - running the tests", ["$ python -m pytest -q"] + tests),
    }


def build_zip(work, zip_path):
    files = sorted(p for p in work.rglob("*") if p.is_file()
                   and not (set(p.relative_to(work).parts) & SKIP_PARTS) and p.name not in SKIP_FILES)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"{SLUG}/{path.relative_to(work).as_posix()}", ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return zipfile.ZipFile(zip_path).namelist()


def draw_page_furniture(canvas, doc):
    """The logo, a rule and the footer, drawn on EVERY page."""
    from reportlab.lib.utils import ImageReader

    canvas.saveState()
    logo = ImageReader(str(LOGO))
    logo_w, logo_h = logo.getSize()
    height = LOGO_W * logo_h / logo_w
    canvas.drawImage(logo, MARGIN_X, PAGE_H - 12 * mm - height, width=LOGO_W, height=height, mask="auto")
    canvas.setStrokeColor(BRAND_BLUE)
    canvas.setLineWidth(1.2)
    rule_y = PAGE_H - HEADER_H + 3 * mm
    canvas.line(MARGIN_X, rule_y, PAGE_W - MARGIN_X, rule_y)

    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_X, 16 * mm, PAGE_W - MARGIN_X, 16 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(MARGIN_X, 11 * mm, "DigiDARA Technologies  |  Example project report")
    canvas.drawRightString(PAGE_W - MARGIN_X, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27,
                                textColor=BRAND_BLUE, alignment=0, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
                                   leading=14, textColor=MUTED, spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19,
                             textColor=BRAND_BLUE, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                             textColor=INK, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15.5,
                               textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
        "note": ParagraphStyle("note", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14,
                               textColor=INK),
    }


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(text, style), leftIndent=14) for text in items],
        bulletType="bullet", start="•", bulletFontSize=11, leftIndent=14, bulletOffsetY=-1,
    )


def build_pdf(pdf_path):
    s = styles()
    story = [
        Paragraph("Expense Tracker - Project Report", s["title"]),
        Paragraph("A command-line program that records and summarises personal spending", s["subtitle"]),
    ]

    note = Table(
        [[Paragraph(
            "<b>EXAMPLE REPORT.</b> This shows the sections and the level of detail the Capstone agent expects. "
            "Your own .docx report needs exactly three sections: <b>Problem Statement</b>, <b>Approach</b> and "
            "<b>Conclusion</b>. Do not paste your code or screenshots into it - your code and your output screenshots "
            "both go in the .zip (the screenshots in its <b>output_screenshots</b> folder). Write about your own "
            "project; do not copy this one.", s["note"])]],
        colWidths=[PAGE_W - 2 * MARGIN_X],
    )
    note.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [note, Spacer(1, 4)]

    story.append(Paragraph("Problem Statement", s["h1"]))
    story.append(Paragraph(
        "People lose track of small everyday spending, so at the end of the month they cannot say where their "
        "money went. Paper notes get lost and spreadsheets are too much effort for a ten-second purchase. This "
        "project builds a small command-line program that records each expense with an amount, a category and a "
        "note, saves it to a file, and shows how much was spent in each category.", s["body"]))
    story.append(Paragraph("The program has to meet these requirements:", s["body"]))
    story.append(bullets([
        "Add an expense with an amount, a category and a note.",
        "Reject invalid input, such as a zero or negative amount or an unknown category.",
        "Keep the data between runs, so closing the program loses nothing.",
        "Show the total spent in each category.",
        "Include automated tests for the rules.",
    ], s["body"]))

    story.append(Paragraph("Approach", s["h1"]))
    story.append(Paragraph(
        "The program is split into three modules so that each one has a single job. This keeps the rules easy to "
        "test and easy to change without touching the file handling or the command line.", s["body"]))
    story.append(bullets([
        "<b>tracker.py</b> holds the rules. It validates an expense and computes category and monthly totals. "
        "It never touches the disk, which makes it simple to test.",
        "<b>storage.py</b> reads and writes the JSON file that holds the expenses.",
        "<b>main.py</b> is the command-line interface, built with argparse, that connects the two.",
    ], s["body"]))
    story.append(Paragraph("Design decisions", s["h2"]))
    story.append(Paragraph(
        "JSON was chosen over a database because the amount of data is small and a plain file needs no setup. "
        "Amounts are rounded to two decimals and stored as numbers so totals add up exactly. The category must "
        "come from a fixed list, so the totals are not split across spellings such as <i>food</i> and "
        "<i>Foood</i>. Validation lives in one place and runs before anything is saved, so a bad value can never "
        "reach the file.", s["body"]))
    story.append(Paragraph("How the requirements are met", s["h2"]))
    story.append(bullets([
        "Adding an expense goes through <i>add_expense</i>, which checks the amount and the category first.",
        "Invalid input is rejected with a clear message and nothing is written.",
        "The expense list is loaded at start-up and saved after every change.",
        "The summary groups expenses by category and prints each total with a simple text bar chart.",
        "The tests cover valid and invalid expenses, the category totals and the monthly total.",
    ], s["body"]))

    story.append(Paragraph("Conclusion", s["h1"]))
    story.append(Paragraph(
        "The program meets all five requirements. It records and validates expenses, keeps them between runs, "
        "summarises spending by category and is covered by seven automated tests. Keeping the rules separate from "
        "the file handling was the most useful decision: it made the code simple to test and simple to change.",
        s["body"]))
    story.append(Paragraph("What I learned", s["h2"]))
    story.append(Paragraph(
        "Deciding what counts as invalid input before writing any code saved time later, and small modules with "
        "one job each are much easier to check than one long script.", s["body"]))
    story.append(Paragraph("Limitations and possible improvements", s["h2"]))
    story.append(bullets([
        "One user only, and saved expenses cannot yet be edited or deleted.",
        "Filtering by date range and exporting to CSV would be natural next steps.",
        "A simple chart of monthly spending would make the summary easier to read.",
    ], s["body"]))

    document = SimpleDocTemplate(
        str(pdf_path), pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=HEADER_H + 4 * mm, bottomMargin=24 * mm, pageCompression=0,
        title="Expense Tracker - Project Report (example)", author="DigiDARA Technologies",
        subject="Capstone example report",
    )
    document.build(story, onFirstPage=draw_page_furniture, onLaterPages=draw_page_furniture)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp) / SLUG
        shutil.copytree(PROJECT, work, ignore=shutil.ignore_patterns(*SKIP_PARTS, "expenses.json"))
        shots = capture(work)
        (work / "output_screenshots").mkdir()
        for filename, (title, lines) in shots.items():
            render_terminal(work / "output_screenshots" / filename, title, lines)
        names = build_zip(work, OUT_DIR / ZIP_NAME)
    build_pdf(OUT_DIR / PDF_NAME)
    print(f"Wrote {OUT_DIR / PDF_NAME} ({(OUT_DIR / PDF_NAME).stat().st_size:,} bytes)")
    print(f"Wrote {OUT_DIR / ZIP_NAME} ({(OUT_DIR / ZIP_NAME).stat().st_size:,} bytes), {len(names)} files:")
    for name in names:
        print("  ", name)


if __name__ == "__main__":
    main()
