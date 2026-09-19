"""PDF invoice / payment receipt for a paid payment.

Seller details come from the environment so nothing legal is invented here:

    INVOICE_COMPANY_NAME      default "DigiDARA"
    INVOICE_COMPANY_ADDRESS   optional, lines separated by "|"
    INVOICE_GSTIN             optional, printed when set
    INVOICE_GST_RATE          optional, e.g. "18". When set, the invoice shows
                              the GST included in the amount paid (prices are
                              treated as tax-inclusive).

The invoice number is derived from the payment, so it is stable and unique but
not a gapless sequence; if statutory serial numbering is required it must be
replaced by a real counter.
"""
import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def invoice_number(payment_id: str, paid_at: datetime) -> str:
    return f"DD-{paid_at:%Y%m}-{payment_id[:8].upper()}"


def money(amount_paise: int, currency: str) -> str:
    # The built-in PDF fonts have no rupee glyph, so print the ISO code.
    return f"{currency} {amount_paise / 100:,.2f}"


def _gst_rate() -> float | None:
    raw = os.environ.get("INVOICE_GST_RATE", "").strip()
    try:
        rate = float(raw)
    except ValueError:
        return None
    return rate if rate > 0 else None


def company_details() -> dict:
    return {
        "name": os.environ.get("INVOICE_COMPANY_NAME", "").strip() or "DigiDARA",
        "address": [line.strip() for line in os.environ.get("INVOICE_COMPANY_ADDRESS", "").split("|") if line.strip()],
        "gstin": os.environ.get("INVOICE_GSTIN", "").strip(),
    }


def build_invoice_pdf(*, payment, description: str, customer: dict) -> bytes:
    """`payment` needs id, amount, currency, razorpay_payment_id, razorpay_order_id, paid_at."""
    company = company_details()
    number = invoice_number(payment.id, payment.paid_at)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=12, textColor=colors.HexColor("#667085"))
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=22, alignment=0, spaceAfter=2, textColor=colors.HexColor("#15161a"))
    label = ParagraphStyle("label", parent=small, textColor=colors.HexColor("#365f91"), fontName="Helvetica-Bold")

    def p(text, style=body):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"Invoice {number}", author=company["name"])
    story = [p("INVOICE", title), p("Payment receipt for your DigiDARA purchase", small), Spacer(1, 8 * mm)]

    seller = [p(company["name"], ParagraphStyle("seller", parent=body, fontName="Helvetica-Bold", fontSize=12))]
    seller += [p(line, body) for line in company["address"]]
    if company["gstin"]:
        seller.append(p(f"GSTIN: {company['gstin']}", body))
    buyer = [p("BILLED TO", label), p(customer.get("name") or "DigiDARA user")]
    for key in ("email", "mobile"):
        if customer.get(key):
            buyer.append(p(customer[key]))
    meta = [
        p("INVOICE NO.", label), p(number), Spacer(1, 2 * mm),
        p("DATE PAID", label), p(f"{payment.paid_at:%d %b %Y}"),
    ]
    header = Table([[seller, buyer, meta]], colWidths=[62 * mm, 62 * mm, 46 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [header, Spacer(1, 10 * mm)]

    total = money(payment.amount, payment.currency)
    rows = [[p("DESCRIPTION", label), p("QTY", label), p("AMOUNT", label)], [p(description), p("1"), p(total)]]
    items = Table(rows, colWidths=[110 * mm, 15 * mm, 45 * mm])
    items.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#d0d5dd")),
        ("LINEBELOW", (0, 1), (-1, 1), 0.4, colors.HexColor("#eaecf0")),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(items)

    totals = []
    rate = _gst_rate()
    if rate:
        taxable = round(payment.amount / (1 + rate / 100))
        totals.append([p("Taxable value"), p(money(taxable, payment.currency))])
        totals.append([p(f"GST @ {rate:g}% (included)"), p(money(payment.amount - taxable, payment.currency))])
    totals.append([p("Total paid", ParagraphStyle("t", parent=body, fontName="Helvetica-Bold", fontSize=12)),
                   p(total, ParagraphStyle("tv", parent=body, fontName="Helvetica-Bold", fontSize=12))])
    summary = Table(totals, colWidths=[125 * mm, 45 * mm])
    summary.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#15161a"))]))
    story += [Spacer(1, 4 * mm), summary, Spacer(1, 12 * mm)]

    story += [
        p("PAYMENT DETAILS", label),
        p(f"Paid online via Razorpay\nPayment ID: {payment.razorpay_payment_id or '-'}\nOrder ID: {payment.razorpay_order_id}"),
        Spacer(1, 12 * mm),
        p("This is a computer-generated document and does not require a signature.", small),
    ]
    doc.build(story)
    return buffer.getvalue()
