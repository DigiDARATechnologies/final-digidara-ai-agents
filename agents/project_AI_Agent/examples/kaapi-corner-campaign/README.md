# Kaapi Corner - Flyer, Landing Page and Google Ads Launch Campaign

A 7-day local launch campaign for **Kaapi Corner**, a hypothetical filter-coffee shop in
RS Puram, Coimbatore: a printed flyer, an SEO-optimised landing page, tracked links,
a small Google Ads search campaign and a first-week Google Analytics review.

## What is in this folder

| Path | What it is |
|------|------------|
| `src/` | The landing page: `index.html`, `styles.css`, `logo.svg`, `robots.txt`, `sitemap.xml` |
| `assets/flyer.png` | The flyer (designed in Canva, exported as PNG) |
| `campaign/keyword-plan.csv` | Target and negative keywords, and where each one is used |
| `campaign/ad-copy.md` | Responsive search ad headlines and descriptions, and the A/B test |
| `campaign/budget-plan.csv` | Google Ads campaign settings and budget |
| `campaign/utm-links.csv` | One tracked link per channel (flyer QR code, Google Ads, Instagram, WhatsApp) |
| `campaign/results-week1.csv` | GA4 traffic and conversion events by source for the first week |
| `tools/seo_audit.py` | A small on-page SEO checker for the landing page |
| `tests/` | Tests for the SEO checker |
| `output_screenshots/` | Screenshots of the page, the flyer, the SEO audit, the ad setup and the analytics |

## How to view and check the landing page

1. Open `src/index.html` in a browser.
2. Run the SEO audit (Python 3.10+, no packages needed):

   ```
   python tools/seo_audit.py src/index.html
   ```

3. Run the tests (`pip install pytest`): `python -m pytest -q`

## Before publishing

- Replace `G-XXXXXXXXXX` in `src/index.html` with your GA4 Measurement ID.
- Mark `whatsapp_order_click` as a key event in GA4 and import it into Google Ads as the conversion.

## About the screenshots

In a real project, `04-google-ads-setup.png` and `05-analytics-week1.png` are screenshots
taken in your own Google Ads and GA4 accounts. Kaapi Corner is hypothetical, so in this
example those two are drawn from `campaign/budget-plan.csv` and `campaign/results-week1.csv`.
