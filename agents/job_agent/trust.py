"""Job Authenticity, Trust & Scam Verification Engine for DigiDARA Job Agent.

Analyzes job listings for college students to ensure postings are genuine, verified,
and free of fraudulent schemes (e.g. upfront training fees, security deposits,
untraceable contacts). Transparently identifies listing source (Adzuna API,
RapidAPI JSearch, or Direct Employer Portal).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

# Aggregator domains
ADZUNA_DOMAINS = {"adzuna.in", "adzuna.com"}
RAPIDAPI_DOMAINS = {"rapidapi.com", "jsearch"}

# Other known external job board domains
JOB_BOARD_DOMAINS = {
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "naukri.com",
    "shine.com",
    "foundit.in",
    "internshala.com",
}

# Red flags / suspicious scam signals
SUSPICIOUS_PHRASES = [
    r"\bregistration fee\b",
    r"\btraining fee\b",
    r"\bsecurity deposit\b",
    r"\bpay\s+(?:us|money|amount)\s+to\s+apply\b",
    r"\btelegram\s+(?:id|channel|group|link)\b",
    r"\bwhatsapp\s+(?:me|resume|at)\s+\+?[0-9]{10,}\b",
    r"\bpart\s*time\s*earn\s*daily\b",
    r"\bdata\s*entry\s*earn\s*[0-9]+k\b",
    r"\bcrypto\s*trading\s*assistant\b",
    r"\bno\s*interview\s*direct\s*joining\s*after\s*payment\b",
]


def candidate_trust_badge(job: Dict[str, Any]) -> str:
    """Expose safety checks without naming ingestion providers to candidates."""
    badge = str(job.get("trust_badge") or "Listing not independently verified")
    return re.sub(r"\s*\(via\s+[^)]*\)", "", badge, flags=re.I)


def candidate_trust_signals(job: Dict[str, Any]) -> List[str]:
    return [re.sub(r"Listing supplied by [^;]+;", "Listing supplied externally;", str(signal))
            for signal in (job.get("signals") or ["No independent verification signals available"])]


def evaluate_job_trust(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates authenticity, safety, and source transparency for a job posting.
    Returns:
    {
        "trust_score": int (0-100),
        "is_verified": bool,
        "trust_badge": str,
        "trust_level": str ("direct_employer" | "aggregator" | "trusted" | "standard" | "caution"),
        "source_label": str,
        "signals": list[str]
    }
    """
    score = 75  # Baseline score for active ingested jobs
    signals: List[str] = []

    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    desc = str(job.get("description") or "").strip()
    apply_url = str(job.get("apply_url") or "").strip()
    source_type = str(job.get("source_type") or job.get("source") or "").lower().strip()
    external_id = str(job.get("external_id") or "").lower().strip()
    combined_text = f"{title} {company} {desc}".lower()

    # 1. Domain & Source Transparency
    parsed_domain = ""
    if apply_url:
        try:
            parsed = urlparse(apply_url)
            parsed_domain = (parsed.netloc or "").lower().replace("www.", "")
        except Exception:
            parsed_domain = ""

    is_adzuna = (
        source_type == "adzuna"
        or (not source_type and ("adzuna" in external_id or any(d in parsed_domain for d in ADZUNA_DOMAINS)))
    )
    is_jsearch = (
        source_type == "jsearch"
        or (not source_type and ("jsearch" in external_id or any(d in parsed_domain for d in RAPIDAPI_DOMAINS)))
    )
    is_direct_career_page = (
        bool(parsed_domain)
        and ("careers." in parsed_domain or "/careers" in apply_url.lower() or "/jobs" in apply_url.lower())
        and not is_adzuna
        and not is_jsearch
        and not any(d in parsed_domain for d in JOB_BOARD_DOMAINS)
    )

    if is_adzuna:
        source_label = "Adzuna Job API"
        score += 3
        signals.append("Listing supplied by Adzuna; employer verification not established")
    elif is_jsearch:
        source_label = "RapidAPI JSearch"
        score += 3
        signals.append("Listing supplied by JSearch; employer verification not established")
    elif is_direct_career_page:
        source_label = "Direct Company Portal"
        score += 15
        signals.append("Direct corporate careers portal")
    elif parsed_domain:
        source_label = parsed_domain
        signals.append(f"Application hosted on {parsed_domain}")
    else:
        source_label = "Standard Tech Feed"

    # 2. Company Authenticity
    if company and company.lower() not in {"unknown", "confidential", "leading mnc"}:
        score += 5
        signals.append(f"Named employer: {company}")
    else:
        score -= 15
        signals.append("Employer name undisclosed")

    # 3. Description Depth & Legitimacy
    if len(desc) >= 300:
        score += 5
        signals.append("Detailed role responsibilities provided")
    elif len(desc) < 80:
        score -= 10
        signals.append("Very brief description")

    # 4. Scam & Fraud Check
    scam_found = False
    for pattern in SUSPICIOUS_PHRASES:
        if re.search(pattern, combined_text):
            scam_found = True
            score -= 40
            signals.append("Flagged: Contains suspicious payment or unverified contact phrasing")
            break

    # 5. Application Link Security
    if apply_url.startswith("https://"):
        score += 5
        signals.append("Secure HTTPS application gateway")
    elif not apply_url:
        score -= 20
        signals.append("Missing application URL")

    # Clamp score
    final_score = max(20, min(99, score))
    if is_adzuna or is_jsearch:
        final_score = min(final_score, 79)
    is_verified = bool(is_direct_career_page and final_score >= 85 and not scam_found)

    # Transparent Badge Assignment (Never misrepresent aggregator as corporate posting)
    if scam_found:
        trust_badge = "⚠️ Review With Caution"
        trust_level = "caution"
    elif is_direct_career_page and final_score >= 85:
        trust_badge = "🏢 Direct Employer Career Page"
        trust_level = "direct_employer"
    elif is_adzuna:
        trust_badge = "📋 Aggregator Listing (via Adzuna)"
        trust_level = "aggregator"
    elif is_jsearch:
        trust_badge = "📋 Aggregator Listing (via RapidAPI JSearch)"
        trust_level = "aggregator"
    elif final_score >= 75:
        trust_badge = "ℹ️ Listing Checks Passed"
        trust_level = "standard"
    elif final_score >= 50:
        trust_badge = "ℹ️ Standard Listing"
        trust_level = "standard"
    else:
        trust_badge = "⚠️ Review With Caution"
        trust_level = "caution"

    if is_direct_career_page:
        application_label = "Apply on company career page"
        verification_note = "Direct career-page signals found; still verify the employer and role before sharing personal data."
    elif is_adzuna or is_jsearch:
        application_label = "Open listing source"
        verification_note = "Aggregator-supplied listing; the employer and vacancy were not independently verified."
    else:
        application_label = "Open application page"
        verification_note = "Source checks are limited; verify the employer and vacancy before applying."

    return {
        "trust_score": final_score,
        "is_verified": is_verified,
        "trust_badge": trust_badge,
        "trust_level": trust_level,
        "source_label": source_label,
        "signals": signals[:3],
        "application_label": application_label,
        "verification_note": verification_note,
    }
