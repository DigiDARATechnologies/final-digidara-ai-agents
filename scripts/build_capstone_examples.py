"""Build the Capstone agent's downloadable example files, once.

Produces, under public/capstone-examples/ (served as static files by the
frontend, so nothing is generated at request time):

    capstone-example-report.docx     a filled-in project report
    capstone-example-project.zip     the matching source-code archive

Both are built from the real, runnable project in
agents/project_AI_Agent/examples/expense-tracker: the program and its tests
are actually executed here and their genuine output is rendered into the
screenshots, so the example is internally consistent. The outputs are
committed; re-run this script only when the example needs to change:

    python scripts/build_capstone_examples.py
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "agents/project_AI_Agent/examples/expense-tracker"
OUT_DIR = ROOT / "public/capstone-examples"
SLUG = "expense-tracker"
ZIP_NAME = "capstone-example-project.zip"
DOCX_NAME = "capstone-example-report.docx"
# Fixed timestamp so rebuilding produces a byte-identical archive.
ZIP_TIME = (2026, 9, 19, 0, 0, 0)
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv"}
SKIP_FILES = {"expenses.json"}  # runtime data written by `add`, never shipped

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
    return [name for name in zipfile.ZipFile(zip_path).namelist()]


def add_code(document, text):
    for line in text.splitlines() or [""]:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        run_ = paragraph.add_run(line or " ")
        run_.font.name, run_.font.size = "Consolas", Pt(9)
        run_.font.color.rgb = RGBColor(0x10, 0x18, 0x28)


def build_docx(work, docx_path):
    doc = Document()
    doc.core_properties.title = "Expense Tracker - Project Report (example)"
    doc.core_properties.author = "DigiDARA Capstone examples"

    doc.add_paragraph("Expense Tracker - Project Report", style="Title")
    note = doc.add_paragraph()
    note.add_run("EXAMPLE REPORT. ").bold = True
    note.add_run("This shows the sections, level of detail and screenshots the Capstone agent expects. "
                 "Write your own report for your own project; do not copy this one.")

    doc.add_heading("Problem Statement", level=1)
    doc.add_paragraph("People lose track of small everyday spending, so at the end of the month they cannot say "
                      "where their money went. This project builds a small command-line program that records each "
                      "expense with an amount, a category and a note, saves it to a file, and shows how much was "
                      "spent in each category.")
    doc.add_paragraph("Requirements: (1) add an expense; (2) reject invalid input; (3) keep data between runs; "
                      "(4) show totals per category; (5) include automated tests.")

    doc.add_heading("Approach", level=1)
    doc.add_paragraph("The program is split into three modules so each has one job:")
    for text in ("tracker.py - the rules: validates an expense and computes category and monthly totals. "
                 "It never touches the disk, which makes it easy to test.",
                 "storage.py - reads and writes the JSON file that holds the expenses.",
                 "main.py - the command-line interface (argparse) that connects the two."):
        doc.add_paragraph(text, style="List Bullet")
    doc.add_paragraph("Design decisions: JSON was chosen over a database because the data is small and a plain "
                      "file needs no setup. Amounts are rounded to two decimals and stored as numbers, and the "
                      "category must come from a fixed list so the totals are not split by typos.")

    doc.add_heading("Code", level=1)
    doc.add_paragraph("Key parts of the source (the full code is in the zip). The code is pasted as text, "
                      "not as a picture, so it can be read and reviewed.")
    doc.add_paragraph("src/tracker.py - validation:")
    tracker = (work / "src/tracker.py").read_text(encoding="utf-8")
    add_code(doc, tracker[tracker.index("def add_expense"):tracker.index("def total_by_category")].rstrip())
    doc.add_paragraph("src/tracker.py - totals per category:")
    add_code(doc, tracker[tracker.index("def total_by_category"):tracker.index("def monthly_total")].rstrip())

    doc.add_heading("Output Screenshots", level=1)
    doc.add_paragraph("Each screenshot below is also saved in the zip under output_screenshots/.")
    shots = [
        ("01-add-expense.png", "Figure 1: adding two expenses, and an invalid amount being rejected."),
        ("02-category-summary.png", "Figure 2: the per-category summary with totals and a text bar chart."),
        ("03-tests-passing.png", "Figure 3: the automated tests all passing."),
    ]
    for filename, caption in shots:
        doc.add_picture(str(work / "output_screenshots" / filename), width=Inches(5.8))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(caption, style="Caption")

    doc.add_heading("Conclusion", level=1)
    doc.add_paragraph("The program meets all five requirements: it records and validates expenses, keeps them "
                      "between runs, summarises spending by category, and is covered by seven passing tests. "
                      "What I learned: keeping the rules separate from file handling made the code simple to test.")
    doc.add_paragraph("Possible improvements: filter by date range, export to CSV, and a simple chart. "
                      "Limitations: one user, and no editing or deleting of saved expenses yet.")
    doc.save(docx_path)


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
        build_docx(work, OUT_DIR / DOCX_NAME)
    print(f"Wrote {OUT_DIR / DOCX_NAME} ({(OUT_DIR / DOCX_NAME).stat().st_size:,} bytes)")
    print(f"Wrote {OUT_DIR / ZIP_NAME} ({(OUT_DIR / ZIP_NAME).stat().st_size:,} bytes), {len(names)} files:")
    for name in names:
        print("  ", name)


if __name__ == "__main__":
    main()
