"""On-page SEO check for the landing page, using only the Python standard library.

    python tools/seo_audit.py src/index.html

Checks the things a search engine and a visitor see first: the title and meta
description lengths, one H1 containing the target keyword, alt text on every
image, a canonical link, the analytics tag and local-business structured data.
"""
import json
import sys
from html.parser import HTMLParser

TARGET_KEYWORD = "filter coffee"
TITLE_RANGE = (30, 60)
DESCRIPTION_RANGE = (70, 160)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.h1 = []
        self.images = []
        self.canonical = False
        self.has_ga4 = False
        self.json_ld = []
        self._in = None
        self._buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content", "")
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = True
        elif tag == "img":
            self.images.append(attrs)
        elif tag == "script" and "googletagmanager.com/gtag/js" in (attrs.get("src") or ""):
            self.has_ga4 = True
        if tag in ("title", "h1") or (tag == "script" and attrs.get("type") == "application/ld+json"):
            self._in, self._buffer = tag, ""

    def handle_data(self, data):
        if self._in:
            self._buffer += data

    def handle_endtag(self, tag):
        if tag != self._in:
            return
        text = " ".join(self._buffer.split())
        if tag == "title":
            self.title = text
        elif tag == "h1":
            self.h1.append(text)
        else:
            self.json_ld.append(text)
        self._in = None


def audit(html):
    """Return a list of (check, passed, detail) tuples."""
    page = PageParser()
    page.feed(html)
    keyword = TARGET_KEYWORD.lower()
    results = []

    n = len(page.title)
    results.append(("Title length", TITLE_RANGE[0] <= n <= TITLE_RANGE[1], f"{n} chars (want {TITLE_RANGE[0]}-{TITLE_RANGE[1]})"))
    results.append(("Keyword in title", keyword in page.title.lower(), f'"{TARGET_KEYWORD}"'))
    n = len(page.description)
    results.append(("Meta description", DESCRIPTION_RANGE[0] <= n <= DESCRIPTION_RANGE[1],
                    f"{n} chars (want {DESCRIPTION_RANGE[0]}-{DESCRIPTION_RANGE[1]})"))
    results.append(("Exactly one H1", len(page.h1) == 1, f"{len(page.h1)} found"))
    results.append(("Keyword in H1", any(keyword in h.lower() for h in page.h1), f'"{TARGET_KEYWORD}"'))
    missing_alt = [img.get("src", "?") for img in page.images if not (img.get("alt") or "").strip()]
    results.append(("Image alt text", not missing_alt,
                    f"{len(page.images) - len(missing_alt)}/{len(page.images)} images have alt text"))
    results.append(("Canonical link", page.canonical, "present" if page.canonical else "missing"))
    results.append(("GA4 tag", page.has_ga4, "gtag.js loaded" if page.has_ga4 else "missing"))
    local = False
    for block in page.json_ld:
        try:
            local = local or "address" in json.loads(block)
        except ValueError:
            pass
    results.append(("Local business schema", local, "JSON-LD with address" if local else "missing"))
    return results


def main(argv):
    path = argv[1] if len(argv) > 1 else "src/index.html"
    with open(path, encoding="utf-8") as handle:
        results = audit(handle.read())
    print(f"SEO audit: {path}")
    for check, passed, detail in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {check:<22} {detail}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"Score: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
