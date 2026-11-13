"""Capstone example files for the Digital Marketing and Prompt Engineering courses.

Those projects are not programs, so the Python expense-tracker example shows
their students the wrong thing. Each course gets its own pair, in the same two
formats as every other project (the submission is still a .docx report and a
.zip with a source folder and an output_screenshots folder):

    capstone-example-report-digital-marketing.pdf
    capstone-example-project-digital-marketing.zip
        from agents/project_AI_Agent/examples/kaapi-corner-campaign: an SEO
        landing page (src/), the flyer, keyword plan, ad copy, UTM links and
        first-week analytics. The page is rendered in headless Chromium for its
        screenshot, and the SEO audit's real output for another.
    capstone-example-report-prompt-engineering.pdf
    capstone-example-project-prompt-engineering.zip
        from agents/project_AI_Agent/examples/support-reply-prompts: three
        prompt versions, test emails, saved responses and the evaluator that
        scores them; its real output is rendered into the screenshots.

Run by scripts/build_capstone_examples.py (which builds the code example too):

    pip install reportlab qrcode playwright && python -m playwright install chromium
    python scripts/build_capstone_examples.py
"""
import csv
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from build_capstone_examples import (
    BRAND_BLUE, HEADER_H, MARGIN_X, OUT_DIR, PAGE_W, ROOT, RULE, SKIP_PARTS, ZIP_TIME,
    bullets, draw_page_furniture, render_terminal, run, styles,
)

EXAMPLES = ROOT / "agents/project_AI_Agent/examples"
SANS = {
    False: ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    True: ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


def load_sans(size, bold=False):
    for candidate in SANS[bold]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise SystemExit("No sans-serif font found; install DejaVu Sans or run on Windows.")


def run_tests(work):
    lines = [line for line in run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work).splitlines()
             if line.strip()]
    if not lines or "passed" not in lines[-1] or "failed" in lines[-1]:
        raise SystemExit(f"Example tests failed in {work.name}:\n" + "\n".join(lines))
    return lines


# --- Images ---------------------------------------------------------------

def render_table(path, title, caption, header, rows):
    """A plain data table as an image, for results kept in CSV files."""
    font, bold, head, small = load_sans(22), load_sans(22, True), load_sans(28, True), load_sans(18)
    pad, row_h = 32, 46
    widths = [max(int(bold.getlength(str(header[i]))), *(int(font.getlength(str(r[i]))) for r in rows)) + 40
              for i in range(len(header))]
    width = max(sum(widths) + pad * 2, int(head.getlength(title)) + pad * 2, int(small.getlength(caption)) + pad * 2)
    top = pad + 78
    height = top + row_h * (len(rows) + 1) + pad
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.text((pad, pad - 6), title, fill="#101828", font=head)
    draw.text((pad, pad + 38), caption, fill="#667085", font=small)
    draw.rectangle([pad, top, width - pad, top + row_h], fill="#eff4ff")
    for index, row in enumerate([header, *rows]):
        y = top + index * row_h
        if index:
            draw.line([pad, y, width - pad, y], fill="#eaecf0", width=1)
        x = pad
        for col, cell in enumerate(row):
            draw.text((x + 16, y + 10), str(cell), fill="#101828", font=bold if index == 0 or col == 0 else font)
            x += widths[col]
    draw.rectangle([0, 0, width - 1, height - 1], outline="#d0d5dd")
    image.save(path, optimize=True)


def render_flyer(path):
    """The A5 flyer: one message (the offer), the details, and a QR code to the page."""
    import qrcode

    w, h = 1240, 1748
    image = Image.new("RGB", (w, h), "#fff7ec")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, w, 560], fill="#5b3416")
    # The same coffee-tumbler logo as src/logo.svg.
    cx = w // 2
    draw.ellipse([cx - 70, 60, cx + 70, 200], fill="#e3a23b")
    draw.polygon([(cx - 34, 120), (cx + 26, 120), (cx + 18, 178), (cx - 26, 178)], fill="#fff7ec")
    draw.arc([cx + 10, 130, cx + 46, 166], start=-90, end=90, fill="#fff7ec", width=7)
    for x in (cx - 16, cx + 4):
        draw.line([(x, 82), (x - 6, 94), (x, 106)], fill="#5b3416", width=5, joint="curve")
    for text, font, y, color in [
        ("KAAPI CORNER", load_sans(84, True), 230, "#ffffff"),
        ("Filter coffee & evening snacks", load_sans(46), 350, "#ffe8c2"),
        ("RS Puram, Coimbatore", load_sans(40), 420, "#ffe8c2"),
        ("20% OFF", load_sans(190, True), 590, "#5b3416"),
        ("your first order", load_sans(60, True), 830, "#5b3416"),
        ("Show this flyer or use code KAAPI20", load_sans(44), 940, "#2b1a0e"),
        ("Open 7am - 10pm, every day", load_sans(40), 1020, "#2b1a0e"),
        ("12 DB Road, RS Puram  |  +91 90000 00000", load_sans(36), 1085, "#2b1a0e"),
    ]:
        draw.text(((w - font.getlength(text)) / 2, y), text, fill=color, font=font)
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data("https://kaapicorner.example/?utm_source=flyer&utm_medium=offline"
                "&utm_campaign=rs_puram_launch&utm_content=qr_front")
    code = qr.make_image(fill_color="#2b1a0e", back_color="#ffffff").get_image().convert("RGB")
    image.paste(code.resize((380, 380), Image.NEAREST), ((w - 380) // 2, 1180))
    label, text = load_sans(34, True), "Scan for the menu & offer"
    draw.text(((w - label.getlength(text)) / 2, 1590), text, fill="#5b3416", font=label)
    draw.rectangle([0, 0, w - 1, h - 1], outline="#e3a23b", width=8)
    image.save(path, optimize=True)


def render_page(html_path, png_path):
    """Screenshot the landing page in headless Chromium, offline (analytics requests blocked)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.route("http*://**", lambda route: route.abort())
        page.goto(html_path.resolve().as_uri())
        page.wait_for_load_state("load")
        page.screenshot(path=str(png_path), full_page=True)
        browser.close()


# --- What goes in each zip -------------------------------------------------

def capture_digital_marketing(work):
    shots = work / "output_screenshots"
    (work / "assets").mkdir()
    render_flyer(work / "assets/flyer.png")
    render_page(work / "src/index.html", shots / "01-landing-page.png")
    shutil.copyfile(work / "assets/flyer.png", shots / "02-flyer.png")
    audit = ["$ python tools/seo_audit.py src/index.html"] + run(
        [sys.executable, "tools/seo_audit.py", "src/index.html"], work).splitlines()
    if not audit[-1].startswith("Score: 9/9"):
        raise SystemExit("The example landing page no longer passes its SEO audit:\n" + "\n".join(audit))
    render_terminal(shots / "03-seo-audit.png", "Terminal - on-page SEO audit", audit)

    with (work / "campaign/budget-plan.csv").open(encoding="utf-8") as handle:
        settings = list(csv.reader(handle))[1:]
    render_table(shots / "04-google-ads-setup.png", "Google Ads - campaign setup",
                 "Kaapi Corner - RS Puram launch (example values from campaign/budget-plan.csv)",
                 ["Setting", "Value"], [[row[0], ", ".join(row[1:])] for row in settings])
    with (work / "campaign/results-week1.csv").open(encoding="utf-8") as handle:
        data = list(csv.DictReader(handle))
    rows = []
    for row in data:
        sessions, orders, cost = int(row["sessions"]), int(row["whatsapp_order_click"]), int(row["cost_inr"])
        rows.append([row["source / medium"], row["users"], sessions, row["claim_offer_click"], orders,
                     f"{orders / sessions:.1%}", f"Rs {cost / orders:.0f}" if cost else "-"])
    render_table(shots / "05-analytics-week1.png", "GA4 - first 7 days by source",
                 "Example values from campaign/results-week1.csv",
                 ["Source / medium", "Users", "Sessions", "Offer clicks", "WhatsApp orders", "Order rate", "Cost / order"],
                 rows)
    run_tests(work)


def capture_prompt_engineering(work):
    shots = work / "output_screenshots"
    compare = ["$ python src/evaluate.py"] + run([sys.executable, "src/evaluate.py"], work).splitlines()
    render_terminal(shots / "01-prompt-comparison.png", "Terminal - comparing prompt versions", compare)
    failures = ["$ python src/evaluate.py --failures v2_role_and_rules"] + run(
        [sys.executable, "src/evaluate.py", "--failures", "v2_role_and_rules"], work).splitlines()
    render_terminal(shots / "02-v2-failures.png", "Terminal - what version 2 got wrong", failures)
    tests = run_tests(work)
    render_terminal(shots / "03-tests-passing.png", "Terminal - running the tests", ["$ python -m pytest -q"] + tests)
    # The report quotes these scores; stop if the example no longer produces them.
    text = "\n".join(compare)
    if not all(score in text for score in ("32.5%", "67.5%", "97.5%")):
        raise SystemExit("The Prompt Engineering scores changed; update the report text:\n" + text)


# --- Reports ----------------------------------------------------------------

def boxed(paragraph):
    table = Table([[paragraph]], colWidths=[PAGE_W - 2 * MARGIN_X])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def data_table(rows, s, widths_mm):
    table = Table([[Paragraph(f"<b>{c}</b>" if i == 0 else str(c), s["note"]) for c in row] for i, row in enumerate(rows)],
                  colWidths=[w * mm for w in widths_mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF4FF")),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_report(pdf_path, title, subtitle, zip_hint, blocks):
    """blocks: ("h1"|"h2"|"p", text), ("ul", [items]) or ("table", rows, column_widths_mm)."""
    s = styles()
    story = [
        Paragraph(title, s["title"]), Paragraph(subtitle, s["subtitle"]),
        boxed(Paragraph(
            "<b>EXAMPLE REPORT.</b> This shows the sections and the level of detail the Capstone agent expects. "
            "Your own .docx report needs exactly three sections: <b>Problem Statement</b>, <b>Approach</b> and "
            f"<b>Conclusion</b>. {zip_hint} Write about your own project; do not copy this one.", s["note"])),
        Spacer(1, 4),
    ]
    for block in blocks:
        if block[0] == "ul":
            story.append(bullets(block[1], s["body"]))
        elif block[0] == "table":
            story += [data_table(block[1], s, block[2]), Spacer(1, 6)]
        else:
            story.append(Paragraph(block[1], s["body" if block[0] == "p" else block[0]]))
    SimpleDocTemplate(
        str(pdf_path), pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=HEADER_H + 4 * mm, bottomMargin=24 * mm, pageCompression=0,
        title=f"{title} (example)", author="DigiDARA Technologies", subject="Capstone example report",
    ).build(story, onFirstPage=draw_page_furniture, onLaterPages=draw_page_furniture)


def digital_marketing_report(pdf_path):
    render_report(
        pdf_path,
        "Kaapi Corner - Local Launch Campaign Report",
        "A flyer, an SEO landing page and a Google Ads campaign for a neighbourhood coffee shop",
        "Do not paste your page code or screenshots into it: the landing page's files, the flyer, your campaign "
        "files and your screenshots (the page, Google Ads setup, GA4 dashboard) all go in the .zip, the "
        "screenshots in its <b>output_screenshots</b> folder.",
        [
            ("h1", "Problem Statement"),
            ("p", "Kaapi Corner is a new filter-coffee shop on DB Road, RS Puram, Coimbatore. It has no website, no "
                  "online reviews and no way to tell which of its promotions bring people in. The owner wants more "
                  "first-time customers in the first week, within a total advertising budget of Rs 2,100, and wants to "
                  "know which channel worked so that next month's budget goes to the right place."),
            ("p", "The campaign had to meet these requirements:"),
            ("ul", ["A printed flyer with the business name, logo, contact details and one clear offer.",
                    "A landing page that matches the flyer and is optimised for local search (keywords, meta tags, "
                    "alt text, structured data).",
                    "Google Analytics 4 on the page, tracking visits and the two actions that matter: claiming the "
                    "offer and ordering on WhatsApp.",
                    "A small Google Ads search campaign that sends people to the page.",
                    "A way to tell flyer visitors apart from ad and social-media visitors."]),
            ("h1", "Approach"),
            ("h2", "Audience and keywords"),
            ("p", "The audience is office workers, college students and residents within about 5 km of RS Puram. "
                  "Keyword research focused on local intent: <i>filter coffee coimbatore</i> (about 1,900 searches a "
                  "month) and <i>filter coffee rs puram</i> became the main keywords, used in the page title, the H1 "
                  "and the first ad group. Negative keywords such as <i>coffee powder</i> and <i>jobs</i> stop the ads "
                  "showing to people who will never visit."),
            ("h2", "Flyer and landing page"),
            ("p", "The flyer carries one message, <b>20% off your first order</b> with code KAAPI20, and a QR code to "
                  "the landing page. The page uses the same colours and offer, so someone who scans the code knows "
                  "they are in the right place. It has a 52-character title and a 145-character meta description that "
                  "both contain the main keyword, one H1, alt text on every image, a canonical link and LocalBusiness "
                  "structured data with the address and opening hours. A small script checks all of this; the page "
                  "passes all 9 checks."),
            ("h2", "Tracking"),
            ("p", "Every channel has its own UTM link (flyer QR code, Google Ads, Instagram, WhatsApp status), so GA4 "
                  "reports each one separately. The two buttons send GA4 events, <i>claim_offer_click</i> and "
                  "<i>whatsapp_order_click</i>. The WhatsApp click is the key event, and it is imported into Google Ads "
                  "as the campaign's conversion."),
            ("h2", "Google Ads"),
            ("p", "A search campaign within 5 km, Rs 300 a day for 7 days, Maximise Clicks with a Rs 12 maximum CPC, "
                  "and ads shown only while the shop is open. Two descriptions were A/B tested with even rotation: "
                  "one leading with the offer, one with the location."),
            ("h1", "Conclusion"),
            ("p", "In the first week the page had 711 users and 84 WhatsApp orders. The results by channel:"),
            ("table", [["Channel", "Sessions", "WhatsApp orders", "Order rate", "Cost per order"],
                       ["Google Ads", "455", "38", "8.4%", "Rs 54"],
                       ["Flyer (QR code)", "151", "29", "19.2%", "printing only"],
                       ["Instagram", "104", "6", "5.8%", "-"],
                       ["WhatsApp status", "70", "11", "15.7%", "-"]], [44, 24, 36, 28, 38]),
            ("p", "Google Ads brought the most visitors, but flyer visitors were more than twice as likely to order, "
                  "because they were already nearby and holding the offer. All five requirements were met. For next "
                  "month the recommendation is to keep the ads to the two best keywords, print a second run of flyers "
                  "for the two colleges, and replace the Instagram post with WhatsApp status updates."),
            ("h2", "What I learned"),
            ("p", "Tracking has to be planned before the campaign starts: without its own UTM link, the flyer's visits "
                  "would have looked like direct traffic and its success would have been invisible."),
            ("h2", "Limitations and possible improvements"),
            ("ul", ["Seven days is too short for Google Ads to optimise; a 30-day test would give firmer numbers.",
                    "A WhatsApp click is not a confirmed sale; counting the KAAPI20 code at the till would be.",
                    "Asking first-week customers for Google reviews would help the shop show up in local map results."]),
        ],
    )


def prompt_engineering_report(pdf_path):
    render_report(
        pdf_path,
        "Customer Support Reply Prompts - Project Report",
        "Designing and testing a prompt that sorts customer emails and drafts replies that follow store policy",
        "Do not paste your prompts, model outputs or screenshots into it: the prompts, test cases, saved responses, "
        "evaluation script and screenshots all go in the .zip, the screenshots in its "
        "<b>output_screenshots</b> folder.",
        [
            ("h1", "Problem Statement"),
            ("p", "Nila Home Store, a hypothetical online home-goods shop, gets the same few kinds of customer email "
                  "every day: damaged items, late deliveries, refund requests and so on. Support staff spend most of "
                  "their time writing similar replies. The goal is a prompt that makes a language model put each email "
                  "in the right category and draft a reply that staff can send after a quick check."),
            ("p", "The prompt has to meet these requirements:"),
            ("ul", ["Put each email in exactly one of eight categories.",
                    "Return JSON, so the support tool can read the category and the reply.",
                    "Never promise a refund the store's policy does not allow.",
                    "Keep replies under 120 words, starting with \"Hi,\" and ending with the team's sign-off.",
                    "Show, with measurements, that each change to the prompt made it better."]),
            ("h1", "Approach"),
            ("h2", "A fixed test set and automatic checks"),
            ("p", "Before writing any prompt, I wrote 8 test emails, one per category, each with its correct category "
                  "and whether a refund is allowed. Three are traps: a refund request outside the 30-day window, an "
                  "exchange that sounds like a refund, and a complaint about a courier that mentions delivery. Every "
                  "response is scored by 5 rule-based checks in Python (valid JSON, correct category, refund-safe, "
                  "length, greeting and sign-off), so every version is judged the same way. The responses are saved, "
                  "so anyone can re-check the scores without calling the model again."),
            ("h2", "Three prompt versions"),
            ("ul", ["<b>v1 baseline</b>: a one-line instruction, to see what the model does with no guidance.",
                    "<b>v2 role and rules</b>: a support-agent role, the eight categories, the refund policy and a "
                    "request for JSON.",
                    "<b>v3 few-shot and strict JSON</b>: the policy as an explicit list, a rule for the "
                    "courier-complaint case, the exact output format, and two worked examples, one showing how to "
                    "turn down a refund politely."]),
            ("p", "Each version was run once per test email at temperature 0.2, and the raw responses were saved."),
            ("h1", "Conclusion"),
            ("table", [["Version", "JSON", "Category", "Refund-safe", "Length", "Format", "Overall"],
                       ["v1 baseline", "0/8", "0/8", "6/8", "7/8", "0/8", "32.5%"],
                       ["v2 role and rules", "7/8", "5/8", "7/8", "8/8", "0/8", "67.5%"],
                       ["v3 few-shot and strict JSON", "8/8", "8/8", "8/8", "8/8", "7/8", "97.5%"]],
             [44, 17, 22, 26, 19, 20, 22]),
            ("p", "The final prompt scores 97.5%, up from 32.5%. Version 1 wrote friendly prose but promised refunds "
                  "the policy does not allow. Version 2 fixed the format, but still mentioned a refund to the 45-day "
                  "customer, called the size exchange a refund request and once put text before the JSON. The worked "
                  "examples in version 3 fixed all three. The one remaining failure is a sign-off with an extra word "
                  "(\"Support Team\"). All five requirements are met."),
            ("h2", "What I learned"),
            ("p", "Worked examples changed the model's behaviour more than extra rules did, especially for saying no "
                  "politely. Writing the test cases first meant every change could be measured instead of judged by "
                  "reading a few replies."),
            ("h2", "Limitations and possible improvements"),
            ("ul", ["Eight emails is a small test set; real emails in Tamil, Hindi and mixed languages should be added.",
                    "Each prompt was run once; running each case several times would show how consistent it is.",
                    "The checks cannot judge tone or accuracy, so a person should still review a sample of replies."]),
        ],
    )


TRACKS = {
    "digital-marketing": ("kaapi-corner-campaign", capture_digital_marketing, digital_marketing_report),
    "prompt-engineering": ("support-reply-prompts", capture_prompt_engineering, prompt_engineering_report),
}


def build_zip(work, zip_path, slug):
    files = sorted(p for p in work.rglob("*") if p.is_file() and not (set(p.relative_to(work).parts) & SKIP_PARTS))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"{slug}/{path.relative_to(work).as_posix()}", ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return zipfile.ZipFile(zip_path).namelist()


def build_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for track, (slug, capture, report) in TRACKS.items():
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / slug
            shutil.copytree(EXAMPLES / slug, work, ignore=shutil.ignore_patterns(*SKIP_PARTS, "results"))
            (work / "output_screenshots").mkdir()
            capture(work)
            zip_path = OUT_DIR / f"capstone-example-project-{track}.zip"
            names = build_zip(work, zip_path, slug)
        pdf_path = OUT_DIR / f"capstone-example-report-{track}.pdf"
        report(pdf_path)
        print(f"Wrote {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
        print(f"Wrote {zip_path} ({zip_path.stat().st_size:,} bytes), {len(names)} files:")
        for name in names:
            print("  ", name)


if __name__ == "__main__":
    build_all()
