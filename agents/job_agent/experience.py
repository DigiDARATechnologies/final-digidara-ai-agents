"""
Experience Extraction and Seniority Classification Engine for DigiDARA Job Agent.

This module guarantees that college students and freshers receive ONLY genuine
entry-level opportunities (0-1 yrs / internships / trainee roles) and are strictly
shielded from roles requiring 3-6 or 4-8 years of experience.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# Positive indicators that a posting is explicitly intended for college freshers / entry-level
FRESHER_POSITIVE_PATTERNS: List[str] = [
    r"\bfreshers?\b",
    r"\binterns?(?:hip)?\b",
    r"\btrainees?\b",
    r"\bgraduate(?:\s+engineer)?\s+trainee\b",
    r"\bget\b",
    r"\bpget\b",
    r"\bjr\.?\b",
    r"\bjunior\b",
    r"\bentry[-\s]level\b",
    r"\bassociate\s+(?:software\s+)?(?:engineer|developer)\b",
    r"\bassociate\s+consultant\s+trainee\b",
    r"\bcampus(?:\s+hire|\s+recruitment)?\b",
    r"\bcollege\s+graduate\b",
    r"\bnew\s+grad\b",
    r"\bearly\s+career\b",
    r"\bapprentice(?:ship)?\b",
    r"\bbatch\s+of\s+202[3-6]\b",
    r"\b0\s*-\s*1\s*(?:years?|yrs?|y\b)\b",
    r"\b0\s*-\s*2\s*(?:years?|yrs?|y\b)\b",
    r"\b0\s*to\s*1\s*(?:years?|yrs?|y\b)\b",
    r"\b0\s*to\s*2\s*(?:years?|yrs?|y\b)\b",
    r"\bno\s+prior\s+experience\s+required\b",
    r"\bno\s+experience\s+required\b",
]

# Disqualifiers that indicate a mid-to-senior level role (3+ to 10+ years)
SENIOR_DISQUALIFIER_PATTERNS: List[str] = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bstaff\b",
    r"\barchitect\b",
    r"\bmanager\b",
    r"\bdirector\b",
    r"\bhead\s+of\b",
    r"\bvp\b",
    r"\bvice\s+president\b",
    r"\bavp\b",
    r"\bassociate\s+(?:director|manager|vice\s+president|principal)\b",
    r"\bchief\b",
    r"\bexpert\b",
    r"\biii\b",
    r"\biv\b",
    r"\b(?:sde|engineer|developer|specialist)\s*(?:-| )?(?:ii|iii|iv|2|3|4)\b",
    r"\b(?:3|4|5|6|7|8|9|10|12|15)\s*\+\s*(?:years?|yrs?|y\b)\b",
    r"\b(?:3|4|5|6|7|8|9|10)\s*(?:-|to)\s*\d+\s*(?:years?|yrs?|y\b)\b",
    r"\bminimum\s*(?:3|4|5|6|7|8)\s*(?:years?|yrs?|y\b)\b",
    r"\bat\s*least\s*(?:3|4|5|6|7|8)\s*(?:years?|yrs?|y\b)\b",
    r"\bmentoring\s+junior\b",
    r"\bsenior-level\b",
    r"\bhands[-\s]on\s+experience\s+of\s+(?:3|4|5|6|7|8)\b",
]


def extract_experience_from_text(title: str = "", description: str = "") -> Tuple[Optional[float], Optional[float]]:
    """
    Parses title and description to extract required minimum and maximum experience years.
    Returns (exp_min, exp_max) as floats or None.
    """
    combined = f"{title or ''}\n{description or ''}"
    if not combined.strip():
        return None, None

    # 1. Check for explicit 0-1 / 0-2 / fresher signals first
    for pat in [
        r"\b0\s*(?:-|to)\s*1\s*(?:years?|yrs?|y\b)",
        r"\b0\s*(?:-|to)\s*2\s*(?:years?|yrs?|y\b)",
        r"\b(?:fresher|freshers|intern|internship|trainee)\b",
        r"\bno\s+experience\s+required\b",
    ]:
        if re.search(pat, combined, re.I):
            # Check if it was something like "freshers not eligible"
            if not re.search(rf"not\s+{pat}", combined, re.I):
                return 0.0, 1.0

    # 2. Check for explicit experience ranges like "3-6 years", "4 to 8 yrs", "5.1-7 years"
    range_match = re.search(
        r"(?:(?:exp|experience)(?:\s+required)?\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|y\b)",
        combined,
        re.I,
    )
    if range_match:
        try:
            e_min = float(range_match.group(1))
            e_max = float(range_match.group(2))
            if e_min <= e_max and e_max <= 40:
                return e_min, e_max
        except (ValueError, TypeError):
            pass

    # 3. Check for "minimum X years", "at least X years", "X+ years of experience"
    min_match = re.search(
        r"(?:(?:minimum|min|at\s*least)\s*)?(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?|y\b)(?:\s+(?:of|relevant|work|hands[-\s]on)\s+experience)?",
        combined,
        re.I,
    )
    if min_match:
        try:
            val = float(min_match.group(1))
            # Guard against false positives like "30 days" or "2024 year"
            if 0.5 <= val <= 30.0:
                return val, None
        except (ValueError, TypeError):
            pass

    return None, None


def classify_job_seniority(job: Dict[str, Any]) -> str:
    """
    Classifies a job into:
    - 'entry': Fresher, Intern, Junior, Trainee, Graduate (0-1.5 years)
    - 'growth': Mid-level, next-step role (2-4 years, or generic titles without fresher proof)
    - 'senior': Senior, Lead, AVP, Manager, 4+ years, II/III/IV level

    CRITICAL RULE FOR PRODUCTION:
    Generic tech postings with plain titles (e.g. "Software Engineer", "React Developer",
    "Data Scientist") that lack explicit fresher keywords are classified as 'growth' (mid-level),
    NEVER defaulted to 'entry'. This prevents college students from receiving 4-6 year jobs.
    """
    title = str(job.get("title") or "").strip()
    desc = str(job.get("description") or "").strip()
    combined_text = f"{title}\n{desc}"

    # 1. Parse experience from database fields or text
    exp_min = job.get("experience_min")
    exp_max = job.get("experience_max")

    if exp_min is None:
        parsed_min, parsed_max = extract_experience_from_text(title, desc)
        if parsed_min is not None:
            exp_min = parsed_min
            if exp_max is None and parsed_max is not None:
                exp_max = parsed_max

    # 2. Check numeric experience thresholds
    if exp_min is not None:
        try:
            e_min = float(exp_min)
            if e_min >= 4.0:
                return "senior"
            if e_min >= 2.0:
                return "growth"
            if e_min <= 1.0:
                # Still check if title explicitly screams "Lead" or "Principal"
                is_senior = any(re.search(pat, title, re.I) for pat in SENIOR_DISQUALIFIER_PATTERNS[:10])
                if not is_senior:
                    return "entry"
        except (ValueError, TypeError):
            pass

    # 3. Check Senior Disqualifier Patterns in Title & Description
    is_senior_disqualified = any(re.search(pat, combined_text, re.I) for pat in SENIOR_DISQUALIFIER_PATTERNS)
    if is_senior_disqualified:
        return "senior"

    # 4. Check Positive Fresher Signals in Title & Description
    is_positive_fresher = any(re.search(pat, combined_text, re.I) for pat in FRESHER_POSITIVE_PATTERNS)
    if is_positive_fresher:
        return "entry"

    # 5. Production Safe Default:
    # A generic title like "Software Engineer", "Full Stack Developer", "Python Developer"
    # with NO experience stated and NO fresher signals is a Mid-Level / Growth role.
    return "growth"


def is_fresher_eligible(job: Dict[str, Any]) -> bool:
    """
    Returns True ONLY if the opportunity is strictly verified as suitable for college
    graduates and freshers (0 to 1 years experience).
    """
    seniority = classify_job_seniority(job)
    if seniority != "entry":
        return False

    exp_min = job.get("experience_min")
    if exp_min is not None:
        try:
            if float(exp_min) > 1.5:
                return False
        except (ValueError, TypeError):
            pass

    title = str(job.get("title") or "")
    desc = str(job.get("description") or "")
    combined = f"{title}\n{desc}"

    # Strict check against senior keywords
    for pat in SENIOR_DISQUALIFIER_PATTERNS:
        if re.search(pat, combined, re.I):
            return False

    return True


def format_experience_badge(job: Dict[str, Any]) -> str:
    """Returns a user-friendly, transparent experience badge for display."""
    seniority = classify_job_seniority(job)
    exp_min = job.get("experience_min")
    exp_max = job.get("experience_max")

    if exp_min is not None and float(exp_min) == 0.0:
        if exp_max is not None and float(exp_max) <= 1.0:
            return "🎓 Fresher (0–1 yrs)"
        return "🎓 Fresher / Entry-Level (0–2 yrs)"

    if exp_min is not None:
        try:
            mn = float(exp_min)
            if exp_max is not None:
                mx = float(exp_max)
                return f"💼 {int(mn) if mn.is_integer() else mn}–{int(mx) if mx.is_integer() else mx} yrs"
            return f"💼 {int(mn) if mn.is_integer() else mn}+ yrs"
        except (ValueError, TypeError):
            pass

    if seniority == "entry":
        return "🎓 Fresher / Entry-Level"
    if seniority == "growth":
        return "🌱 Junior / Mid-Level (2–4 yrs)"
    return "🚀 Experienced Role (4+ yrs)"
