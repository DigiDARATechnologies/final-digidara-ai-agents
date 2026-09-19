"""The Capstone example downloads (public/capstone-examples) stay well-formed.

They are built once by scripts/build_capstone_examples.py and committed, so
these checks guard the committed bytes: the structure the Capstone agent's
validators look for, and consistency between the report and the zip. Stdlib
only, so it runs anywhere the unit suite does.
"""
import hashlib
import re
import zipfile
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[2] / "public" / "capstone-examples"
DOCX = EXAMPLES / "capstone-example-report.docx"
ZIP = EXAMPLES / "capstone-example-project.zip"
SLUG = "expense-tracker"
REQUIRED_SECTIONS = ["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"]
REQUIRED_PATHS = [
    f"{SLUG}/README.md", f"{SLUG}/requirements.txt", f"{SLUG}/src/main.py", f"{SLUG}/src/tracker.py",
    f"{SLUG}/src/storage.py", f"{SLUG}/tests/test_tracker.py",
]
SCREENSHOTS = ["01-add-expense.png", "02-category-summary.png", "03-tests-passing.png"]


def zip_names():
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        return archive.namelist()


def test_zip_has_one_root_folder_with_the_expected_layout():
    names = zip_names()
    assert {name.split("/")[0] for name in names} == {SLUG}
    for required in REQUIRED_PATHS:
        assert required in names, f"missing {required}"
    for shot in SCREENSHOTS:
        assert f"{SLUG}/output_screenshots/{shot}" in names


def test_zip_contains_no_build_clutter_or_runtime_data():
    for name in zip_names():
        assert "__pycache__" not in name and ".pytest_cache" not in name and ".venv" not in name
        assert name.rsplit("/", 1)[-1] != "expenses.json", "runtime data must not be shipped"
        assert ".." not in name.split("/") and not name.startswith("/")


def test_screenshots_are_real_png_files():
    with zipfile.ZipFile(ZIP) as archive:
        for shot in SCREENSHOTS:
            data = archive.read(f"{SLUG}/output_screenshots/{shot}")
            assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 2_000


def docx_parts():
    with zipfile.ZipFile(DOCX) as archive:
        assert archive.testzip() is None
        xml = archive.read("word/document.xml").decode("utf-8")
        media = {name: archive.read(name) for name in archive.namelist() if name.startswith("word/media/")}
    return xml, media


def test_report_has_every_required_section_as_a_heading():
    xml, _ = docx_parts()
    headings = []
    for paragraph in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        style = re.search(r'<w:pStyle w:val="([^"]+)"', paragraph)
        if style and style.group(1).lower().startswith("heading"):
            headings.append("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paragraph)).strip())
    assert headings == REQUIRED_SECTIONS


def test_report_embeds_exactly_the_screenshots_that_are_in_the_zip():
    _, media = docx_parts()
    assert len(media) == len(SCREENSHOTS)
    with zipfile.ZipFile(ZIP) as archive:
        in_zip = {hashlib.sha256(archive.read(f"{SLUG}/output_screenshots/{shot}")).hexdigest() for shot in SCREENSHOTS}
    in_docx = {hashlib.sha256(data).hexdigest() for data in media.values()}
    assert in_docx == in_zip


def test_report_code_is_text_not_a_picture():
    xml, _ = docx_parts()
    assert "def add_expense" in xml and "def total_by_category" in xml
