"""Conservative compensation extraction for incomplete provider records."""
from __future__ import annotations

import re
from typing import Optional


_SALARY_PATTERNS = (
    re.compile(r"(?:₹|rs\.?|inr)\s*[\d,.]+\s*(?:-|–|to)\s*(?:₹|rs\.?|inr)?\s*[\d,.]+\s*(?:lpa|lakhs?|lacs?|per\s+annum|p\.?a\.?)?", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:lpa|lakhs?|lacs?)\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?|lacs?)\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?|lacs?)\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:lpa|lakhs?|lacs?)\b", re.I),
    re.compile(r"(?:₹|rs\.?|inr)\s*[\d,.]+\s*(?:per\s+(?:month|annum|year)|monthly|annually|p\.?a\.?)", re.I),
)


def extract_salary_text(title: str = "", description: str = "") -> Optional[str]:
    """Return salary text explicitly present in a title/description, or None.

    This never estimates compensation. It only recovers a value providers may
    have embedded in free text while leaving the structured salary field empty.
    """
    for source in (title or "", description or ""):
        for pattern in _SALARY_PATTERNS:
            match = pattern.search(source)
            if match:
                return re.sub(r"\s+", " ", match.group(0)).strip(" -–,|()[]")
    return None
