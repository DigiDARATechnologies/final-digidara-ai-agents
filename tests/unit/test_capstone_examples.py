"""The Capstone example downloads (public/capstone-examples) stay well-formed.

They are built once by scripts/build_capstone_examples.py and committed, so
these checks guard the committed bytes: the example zip's layout, and the
example report PDF (three sections, no code, no screenshots, the logo on every
page). Stdlib only, so it runs anywhere the unit suite does -- the PDF is
written uncompressed and deterministically precisely so it can be inspected
here without a PDF library.
"""
import re
import zipfile
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[2] / "public" / "capstone-examples"
PDF = EXAMPLES / "capstone-example-report.pdf"
ZIP = EXAMPLES / "capstone-example-project.zip"
LOGO = Path(__file__).resolve().parents[2] / "scripts" / "assets" / "digidara-technologies-logo.png"
SLUG = "expense-tracker"
REPORT_SECTIONS = ["Problem Statement", "Approach", "Conclusion"]
RETIRED_SECTIONS = ["Output Screenshots"]
REQUIRED_PATHS = [
    f"{SLUG}/README.md", f"{SLUG}/requirements.txt", f"{SLUG}/src/main.py", f"{SLUG}/src/tracker.py",
    f"{SLUG}/src/storage.py", f"{SLUG}/tests/test_tracker.py",
]


def zip_names():
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        return archive.namelist()


def test_zip_has_one_root_folder_with_the_expected_layout():
    names = zip_names()
    assert {name.split("/")[0] for name in names} == {SLUG}
    for required in REQUIRED_PATHS:
        assert required in names, f"missing {required}"


def test_zip_has_no_screenshots_folder_or_images():
    for name in zip_names():
        assert "screenshot" not in name.lower(), f"{name}: screenshots are not part of a submission any more"
        assert not name.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))


def test_zip_contains_no_build_clutter_or_runtime_data():
    for name in zip_names():
        assert "__pycache__" not in name and ".pytest_cache" not in name and ".venv" not in name
        assert name.rsplit("/", 1)[-1] != "expenses.json", "runtime data must not be shipped"
        assert ".." not in name.split("/") and not name.startswith("/")


def pdf_bytes():
    data = PDF.read_bytes()
    assert data.startswith(b"%PDF-")
    return data


def test_the_example_report_is_a_pdf_and_there_is_no_docx_example():
    pdf_bytes()
    assert not list(EXAMPLES.glob("*.docx")), "the example report is a PDF; only the student's own report is a .docx"


def test_report_has_exactly_the_three_required_sections_and_nothing_retired():
    data = pdf_bytes()
    for section in REPORT_SECTIONS:
        assert section.encode() in data, f"missing section: {section}"
    for section in RETIRED_SECTIONS:
        assert section.encode() not in data, f"{section} is no longer a report section"


def test_report_contains_no_pasted_code():
    data = pdf_bytes()
    for snippet in (b"def add_expense", b"def total_by_category", b"import argparse"):
        assert snippet not in data


def test_report_has_no_embedded_screenshots_only_the_logo():
    data = pdf_bytes()
    images = re.findall(rb"/Subtype /Image", data)
    assert len(images) == 1, "the only image in the report should be the logo"


def test_the_logo_is_drawn_on_every_single_page():
    data = pdf_bytes()
    pages = len(re.findall(rb"/Type /Page\b(?!s)", data))
    logo_draws = re.findall(rb"/(FormXob\.[0-9a-f]+) Do", data)
    assert pages >= 2, "the example should span more than one page for this check to mean anything"
    assert len(logo_draws) == pages, "every page must draw the logo exactly once"
    assert len(set(logo_draws)) == 1, "every page draws the same logo image"


def test_the_embedded_logo_is_the_committed_digidara_logo():
    data = pdf_bytes()
    logo = LOGO.read_bytes()
    width, height = int.from_bytes(logo[16:20], "big"), int.from_bytes(logo[20:24], "big")
    image_header = re.search(rb"/Subtype /Image[^>]*?/Width (\d+)", data, re.S)
    assert image_header is not None and int(image_header.group(1)) == width
    assert re.search(rb"/Height %d\b" % height, data)
