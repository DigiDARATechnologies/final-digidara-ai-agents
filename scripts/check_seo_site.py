"""SEO checks for the public site. Standard library only.

    python scripts/check_seo_site.py                     # the built site in dist/ (run `npm run build` first)
    python scripts/check_seo_site.py https://www.skilldara.com   # a deployed site: status codes, redirects, headers

Static mode checks the JSON-LD on every public page, the sitemap against the real files and canonicals,
and robots.txt. Live mode also checks HTTP status codes, redirects and the noindex headers. Exit code 1 if
any check fails.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = "https://www.skilldara.com"
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def nodes(html: str):
    """Every JSON-LD node on a page, @graph flattened. Raises on invalid JSON."""
    for block in LD.findall(html):
        data = json.loads(block)
        yield from (data["@graph"] if isinstance(data, dict) and "@graph" in data else [data])


def static_checks() -> None:
    if not (DIST / "index.html").is_file():
        sys.exit("dist/ not found: run `npm run build` first")
    pages = {"/": DIST / "index.html"}
    for p in sorted(DIST.rglob("index.html")):
        rel = p.relative_to(DIST).parent.as_posix()
        if rel != ".":
            pages[f"/{rel}/"] = p

    print("\n== JSON-LD (every public page)")
    for url, f in pages.items():
        html = f.read_text(encoding="utf8")
        try:
            ns = list(nodes(html))
        except json.JSONDecodeError as exc:
            check(False, f"{url} JSON-LD parses", str(exc))
            continue
        types = [n.get("@type") for n in ns]
        check(all(n.get("@context", "https://schema.org") for n in ns), f"{url} JSON-LD parses ({len(ns)} nodes)")
        for t in ("Organization", "WebSite", "SoftwareApplication", "FAQPage", "BreadcrumbList"):
            check(types.count(t) <= 1, f"{url} has at most one {t}", f"found {types.count(t)}")
        ids = [n["@id"] for n in ns if "@id" in n]
        check(len(ids) == len(set(ids)), f"{url} no duplicate @id")
        m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        check(bool(m) and m.group(1) == f"{SITE}{url}", f"{url} canonical is {SITE}{url}", m.group(1) if m else "missing")
        check('name="robots" content="index' in html, f"{url} is indexable")

    print("\n== Home page entity graph")
    home = {n["@id"]: n for n in nodes(pages["/"].read_text(encoding="utf8")) if "@id" in n}
    org, brand, site, app = (home.get(f"{SITE}/#{k}", {}) for k in ("org", "brand", "website", "app"))
    check(org.get("@type") == "Organization" and org.get("name") == "DigiDARA Technologies", "Organization is DigiDARA Technologies")
    check(brand.get("@type") == "Brand" and brand.get("name") == "SkillDARA", "Brand is SkillDARA")
    check(org.get("brand") == {"@id": f"{SITE}/#brand"}, "Organization.brand points to the Brand")
    check(site.get("name") == "SkillDARA" and "Skill Dara" in site.get("alternateName", []), "WebSite name SkillDARA, alternateName Skill Dara")
    check(site.get("url") == f"{SITE}/", "WebSite url is the canonical home page")
    check(site.get("publisher") == {"@id": f"{SITE}/#org"}, "WebSite.publisher points to the Organization")
    check(app.get("publisher") == {"@id": f"{SITE}/#org"} and app.get("brand") == {"@id": f"{SITE}/#brand"}, "SoftwareApplication points to the Organization and Brand")
    logo = org.get("logo", {}).get("url", "")
    check(logo.startswith(SITE) and (DIST / logo.replace(SITE + "/", "")).is_file(), "Organization logo file exists", logo)
    check("sameAs" not in org, "no sameAs yet (add only verified official profiles)")

    print("\n== Inner pages point at the same Organization")
    for url, f in pages.items():
        if url == "/":
            continue
        for n in nodes(f.read_text(encoding="utf8")):
            pub = n.get("publisher") or n.get("manufacturer")
            if pub:
                check(pub.get("@id") == f"{SITE}/#org", f"{url} {n.get('@type')} publisher uses the Organization @id")

    print("\n== Sitemap")
    tree = ET.parse(DIST / "sitemap.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [(u.find("s:loc", ns).text, u.find("s:lastmod", ns).text) for u in tree.getroot().findall("s:url", ns)]
    check(len(locs) == len({l for l, _ in locs}), f"no duplicate URLs ({len(locs)} URLs)")
    check(all(l.startswith(SITE + "/") for l, _ in locs), "every URL uses the canonical https://www host")
    check(not any(l.rstrip("/").endswith("/login") for l, _ in locs), "login is not in the sitemap")
    check(set(l.replace(SITE, "") for l, _ in locs) == set(pages), "sitemap lists exactly the public pages")
    check(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") for _, d in locs), "lastmod values are valid dates")

    print("\n== robots.txt")
    robots = (DIST / "robots.txt").read_text(encoding="utf8")
    check(f"Sitemap: {SITE}/sitemap.xml" in robots, "robots.txt lists the sitemap")
    disallowed = re.findall(r"^Disallow:\s*(\S+)", robots, re.M)
    check(not any(d in ("/", "/agents/", "/pricing/", "/faq/", "/for-colleges/", "/login") for d in disallowed), "robots.txt blocks no public page or noindex page", ", ".join(disallowed))

    print("\n== Icons")
    for f in ("favicon.ico", "favicon-48.png", "favicon-96.png", "favicon-192.png", "apple-touch-icon.png", "skilldara-logo-square.png", "og-image.png", "404.html"):
        check((DIST / f).is_file(), f"{f} is in the build")
    check("/favicon.ico" in pages["/"].read_text(encoding="utf8"), "home page links /favicon.ico")


def fetch(url: str):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(urllib.request.Request(url, headers={"User-Agent": "skilldara-seo-check"}), timeout=25)
    except urllib.error.HTTPError as exc:
        r = exc
    return r.status if hasattr(r, "status") else r.code, r.headers


def live_checks(base: str) -> None:
    base = base.rstrip("/")
    token = "A" * 24
    # (path, status, Location (or None), expects noindex)
    cases = [
        ("/", 200, None, False), ("/agents/", 200, None, False), ("/pricing/", 200, None, False), ("/faq/", 200, None, False),
        ("/for-colleges/", 200, None, False), ("/agents/coding-practice/", 200, None, False), ("/agents/job-agent/", 200, None, False),
        ("/agents", 301, "/agents/", False), ("/pricing", 301, "/pricing/", False), ("/faq", 301, "/faq/", False),
        ("/for-colleges", 301, "/for-colleges/", False), ("/agents/mock-interview", 301, "/agents/mock-interview/", False),
        ("/login", 200, None, True), (f"/shared/chat/{token}", 200, None, True), (f"/certificate-link/{token}", 200, None, True),
        (f"/assessment/{token}", 200, None, True),
        ("/nonexistent-page-xyz", 404, None, False),
        ("/favicon.ico", 200, None, False), ("/favicon-48.png", 200, None, False), ("/favicon-192.png", 200, None, False),
        ("/skilldara-logo-square.png", 200, None, False), ("/sitemap.xml", 200, None, False), ("/robots.txt", 200, None, False),
    ]
    print(f"\n== Live checks against {base}")
    for path, want, loc, noindex in cases:
        status, headers = fetch(base + path)
        tag = headers.get("X-Robots-Tag", "") or ""
        ok = status == want and (loc is None or (headers.get("Location", "").replace(base, "") == loc)) and (("noindex" in tag) == noindex)
        check(ok, f"{path} -> {status}{' ' + headers.get('Location', '') if loc else ''}{' noindex' if 'noindex' in tag else ''}",
              f"wanted {want}{' ' + loc if loc else ''}{' noindex' if noindex else ' indexable'}")
    status, headers = fetch(base + "/favicon.ico")
    check(headers.get_content_type().startswith("image/"), "/favicon.ico is an image, not the home page", headers.get_content_type())
    for variant in ("http://skilldara.com/", "https://skilldara.com/", "http://www.skilldara.com/"):
        if base == SITE:
            status, headers = fetch(variant)
            check(status == 301 and headers.get("Location") == f"{SITE}/", f"{variant} redirects to {SITE}/", f"{status} {headers.get('Location')}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        live_checks(sys.argv[1])
    else:
        static_checks()
    print("\nFAILED:" if failures else "\nAll checks passed.", *failures, sep="\n  " if failures else "")
    sys.exit(1 if failures else 0)
