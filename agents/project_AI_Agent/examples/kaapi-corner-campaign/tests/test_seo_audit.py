from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from seo_audit import audit  # noqa: E402

PAGE = Path(__file__).resolve().parents[1] / "src" / "index.html"


def results_for(html):
    return {check: passed for check, passed, _ in audit(html)}


def test_the_landing_page_passes_every_check():
    assert all(results_for(PAGE.read_text(encoding="utf-8")).values())


def test_missing_alt_text_is_caught():
    html = '<html><head><title>Filter coffee in RS Puram, Coimbatore</title></head><body><img src="a.png"></body></html>'
    assert results_for(html)["Image alt text"] is False


def test_two_h1_headings_fail():
    html = "<h1>Filter coffee</h1><h1>Snacks</h1>"
    assert results_for(html)["Exactly one H1"] is False


def test_short_title_fails():
    assert results_for("<title>Cafe</title>")["Title length"] is False
