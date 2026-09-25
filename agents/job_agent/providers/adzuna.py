import logging
import os
import re
from datetime import datetime, timezone
import requests

from ..config import SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT
from ..scraper import ScraperError, _iso_datetime, _text

logger = logging.getLogger(__name__)

ADZUNA_API_BASE = "https://api.adzuna.com/v1/api/jobs/in/search"
ADZUNA_APP_ID_ENV = "ADZUNA_APP_ID"
ADZUNA_APP_KEY_ENV = "ADZUNA_APP_KEY"


class AdzunaNotConfigured(ScraperError):
    pass


class AdzunaAPIError(ScraperError):
    pass


def is_configured():
    return bool(os.getenv(ADZUNA_APP_ID_ENV, "").strip() and os.getenv(ADZUNA_APP_KEY_ENV, "").strip())


def _credentials():
    app_id = os.getenv(ADZUNA_APP_ID_ENV, "").strip()
    app_key = os.getenv(ADZUNA_APP_KEY_ENV, "").strip()
    if not app_id or not app_key:
        raise AdzunaNotConfigured(
            f"{ADZUNA_APP_ID_ENV} or {ADZUNA_APP_KEY_ENV} is not set; Adzuna collection is skipped"
        )
    return app_id, app_key


def _work_mode(text):
    lowered = (text or "").lower()
    if "remote" in lowered or "telecommute" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    return "onsite"


def _salary_text(raw_job):
    min_sal = raw_job.get("salary_min")
    max_sal = raw_job.get("salary_max")
    if min_sal and max_sal:
        return f"\u20b9{int(min_sal):,} - \u20b9{int(max_sal):,}"
    if min_sal:
        return f"From \u20b9{int(min_sal):,}"
    if max_sal:
        return f"Up to \u20b9{int(max_sal):,}"
    return ""


def normalize_job(raw_job):
    """Normalize one raw Adzuna item into the canonical DigiDARA job dictionary."""
    if not isinstance(raw_job, dict):
        return None

    raw_id = raw_job.get("id")
    title = _text(raw_job.get("title"))
    apply_url = str(raw_job.get("redirect_url") or "").strip()

    if not raw_id or not title or not apply_url:
        return None

    source_job_id = str(raw_id).strip()
    company_info = raw_job.get("company") or {}
    company_name = _text(company_info.get("display_name") if isinstance(company_info, dict) else company_info) or "Unknown Company"

    loc_info = raw_job.get("location") or {}
    location_name = _text(loc_info.get("display_name") if isinstance(loc_info, dict) else loc_info)

    description = _text(raw_job.get("description") or "")
    contract_time = str(raw_job.get("contract_time") or "").replace("_", " ").title()

    # Extract clean ISO timestamp
    created_at = _iso_datetime(raw_job.get("created"))
    combined_text = f"{title} {location_name} {description}"

    # Seniority check: filter out extreme executive/AVP titles
    title_lower = title.lower()
    extreme_senior_words = ["avp", "vice president", "director", "head of", "principal", "chief", "staff software"]
    entry_words = ["junior", "jr", "associate", "trainee", "intern", "fresher", "graduate"]
    if any(re.search(r"\b" + re.escape(w) + r"\b", title_lower) for w in extreme_senior_words):
        if not any(re.search(r"\b" + re.escape(w) + r"\b", title_lower) for w in entry_words):
            return None

    # Extract experience years from title/description if present
    from ..experience import extract_experience_from_text
    exp_min, exp_max = extract_experience_from_text(title, description)
    if exp_min is not None and isinstance(exp_min, float) and exp_min.is_integer():
        exp_min = int(exp_min)
    if exp_max is not None and isinstance(exp_max, float) and exp_max.is_integer():
        exp_max = int(exp_max)

    return {
        "source": "adzuna",
        "source_job_id": source_job_id,
        "external_id": f"adzuna:{source_job_id}",
        "title": title,
        "company": company_name,
        "location": location_name,
        "work_mode": _work_mode(combined_text),
        "employment_type": contract_time or "Full Time",
        "experience_min": exp_min,
        "experience_max": exp_max,
        "salary_text": _salary_text(raw_job),
        "description": description,
        "skills": [],
        "apply_url": apply_url,
        "source_url": apply_url,
        "published_at": created_at,
        "expires_at": None,
    }


def fetch_and_normalize(what, where, page=1, results_per_page=20, session=None):
    """Query Adzuna's India job search endpoint and return normalized jobs."""
    app_id, app_key = _credentials()
    session = session or requests.Session()

    url = f"{ADZUNA_API_BASE}/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": what,
        "where": where,
        "results_per_page": min(50, max(1, results_per_page)),
        "content-type": "application/json",
    }
    headers = {
        "User-Agent": SCRAPER_USER_AGENT,
        "Accept": "application/json",
    }

    try:
        response = session.get(url, params=params, headers=headers, timeout=SCRAPER_TIMEOUT_SECONDS)
    except requests.Timeout as exc:
        raise AdzunaAPIError(f"Timed out contacting Adzuna ({url})") from exc
    except requests.RequestException as exc:
        raise AdzunaAPIError(f"Adzuna request failed: {exc}") from exc

    if response.status_code != 200:
        raise AdzunaAPIError(f"Adzuna returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        data = response.json()
    except ValueError as exc:
        raise AdzunaAPIError("Adzuna response is not valid JSON") from exc

    results = data.get("results") or []
    jobs = []
    for item in results:
        normalized = normalize_job(item)
        if normalized:
            jobs.append(normalized)

    return jobs
