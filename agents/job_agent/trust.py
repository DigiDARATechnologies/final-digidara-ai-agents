"""Job Authenticity, Trust & Scam Verification Engine for DigiDARA Job Agent.

Analyzes job listings for college students to ensure postings are genuine, verified,
and free of fraudulent schemes (e.g. upfront training fees, security deposits,
untraceable contacts).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

# Trusted ATS / Career Portal domains that indicate verified corporate listings
TRUSTED_ATS_DOMAINS = {
    "greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "icims.com",
    "taleo.net",
    "bamboohr.com",
    "workable.com",
    "jobvite.com",
    "adzuna.in",
    "adzuna.com",
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "naukri.com",
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


def evaluate_job_trust(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates authenticity and safety score for a job posting.
    Returns:
    {
        "trust_score": int (0-100),
        "is_verified": bool,
        "trust_badge": str,
        "trust_level": str ("verified" | "trusted" | "standard" | "caution"),
        "signals": list[str]
    }
    """
    score = 75  # Baseline score for active ingested jobs
    signals: List[str] = []

    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    desc = str(job.get("description") or "").strip()
    apply_url = str(job.get("apply_url") or "").strip()
    combined_text = f"{title} {company} {desc}".lower()

    # 1. Domain & ATS Evaluation
    parsed_domain = ""
    if apply_url:
        try:
            parsed = urlparse(apply_url)
            parsed_domain = (parsed.netloc or "").lower().replace("www.", "")
        except Exception:
            parsed_domain = ""

    is_ats = any(trusted in parsed_domain for trusted in TRUSTED_ATS_DOMAINS)
    if is_ats:
        score += 15
        signals.append("Verified enterprise ATS / official job portal")
    elif parsed_domain and ("careers" in parsed_domain or "jobs" in parsed_domain):
        score += 10
        signals.append("Direct corporate careers portal")

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
    is_verified = final_score >= 85 and not scam_found

    if final_score >= 90:
        trust_badge = "🛡️ Verified Corporate Posting"
        trust_level = "verified"
    elif final_score >= 75:
        trust_badge = "✅ Genuine Opportunity"
        trust_level = "trusted"
    elif final_score >= 50:
        trust_badge = "ℹ️ Standard Listing"
        trust_level = "standard"
    else:
        trust_badge = "⚠️ Review With Caution"
        trust_level = "caution"

    return {
        "trust_score": final_score,
        "is_verified": is_verified,
        "trust_badge": trust_badge,
        "trust_level": trust_level,
        "signals": signals[:3],
    }
