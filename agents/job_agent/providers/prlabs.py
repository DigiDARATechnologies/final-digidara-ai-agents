"""PR Labs Jobs Search API (prlabsapi.com): LinkedIn / Indeed listings by
role and location.

    POST https://api0.prlabsapi.com/getjobs
    header  api_key: <PRLABS_API_KEY>
    body    {search_term, location, results_wanted, site_name: [...],
             distance, job_type, is_remote, linkedin_fetch_description,
             hours_old}
    reply   {"status": "True", "jobs": [{id, site, job_url, job_url_direct,
             title, company, location, date_posted, job_type, min_amount,
             max_amount, currency, interval, is_remote, description,
             skills, ...}]}

Every field in a job comes back as a string ('' when unknown). The key is
read from the environment only, never from providers.yaml or the database.
"""
import hashlib
import logging
import os

import requests

from ..config import SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT
from ..scraper import ScraperError, _iso_datetime, _text

logger = logging.getLogger(__name__)

PRLABS_JOBS_URL = "https://api0.prlabsapi.com/getjobs"
PRLABS_API_KEY_ENV = "PRLABS_API_KEY"
# LinkedIn scraping on their side takes a while for 50 results.
PRLABS_TIMEOUT_SECONDS = 150


class PRLabsNotConfigured(ScraperError):
    pass


class PRLabsAPIError(ScraperError):
    pass


def is_configured():
    return bool(os.getenv(PRLABS_API_KEY_ENV, "").strip())


def _api_key():
    key = os.getenv(PRLABS_API_KEY_ENV, "").strip()
    if not key:
        raise PRLabsNotConfigured(f"{PRLABS_API_KEY_ENV} is not set; PR Labs collection is skipped until it is configured")
    return key


def _make_external_id(source_job_id):
    if len(source_job_id) <= 240:
        return f"prlabs:{source_job_id}"
    digest = hashlib.sha256(source_job_id.encode("utf-8")).hexdigest()
    return f"prlabs:{source_job_id[:180]}_{digest[:32]}"


def _number(value):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _salary_text(raw_job):
    low, high = _number(raw_job.get("min_amount")), _number(raw_job.get("max_amount"))
    currency = _text(raw_job.get("currency")) or "₹"
    interval = _text(raw_job.get("interval"))
    per = f" / {interval}" if interval else ""
    if low and high:
        return f"{currency} {int(low):,} - {currency} {int(high):,}{per}"
    if low:
        return f"From {currency} {int(low):,}{per}"
    if high:
        return f"Up to {currency} {int(high):,}{per}"
    return ""


def _is_true(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def normalize_job(raw_job):
    """One PR Labs job -> the canonical DigiDARA job dictionary (None if unusable)."""
    if not isinstance(raw_job, dict):
        return None
    job_id = _text(raw_job.get("id"))
    title = _text(raw_job.get("title"))
    apply_url = str(raw_job.get("job_url_direct") or raw_job.get("job_url") or "").strip()
    if not job_id or not title or not apply_url.startswith(("https://", "http://")):
        return None

    skills = raw_job.get("skills") or []
    if isinstance(skills, str):
        skills = [part.strip() for part in skills.split(",") if part.strip()]

    return {
        "source": "prlabs",
        "source_job_id": job_id,
        "external_id": _make_external_id(job_id),
        "title": title,
        "company": _text(raw_job.get("company")) or "Unknown Company",
        "location": _text(raw_job.get("location")),
        "work_mode": "remote" if _is_true(raw_job.get("is_remote")) else "onsite",
        "employment_type": _text(raw_job.get("job_type")).replace("fulltime", "Full Time") or "Full Time",
        "salary_text": _salary_text(raw_job),
        "description": _text(raw_job.get("description")),
        "skills": skills,
        "apply_url": apply_url,
        "source_url": str(raw_job.get("job_url") or apply_url).strip(),
        "published_at": _iso_datetime(raw_job.get("date_posted")) if raw_job.get("date_posted") else None,
        "expires_at": None,
    }


def fetch_and_normalize(search_term, location, results_wanted=50, sites=None, hours_old=168,
                        session=None, before_request=None):
    """Search one role in one location; returns canonical job dicts."""
    key = _api_key()
    session = session or requests.Session()
    payload = {
        "search_term": search_term,
        "location": location,
        "results_wanted": int(results_wanted),
        "site_name": list(sites or ["linkedin", "indeed"]),
        "distance": 50,
        "is_remote": False,
        "linkedin_fetch_description": False,
        "hours_old": int(hours_old),
    }
    headers = {"Content-Type": "application/json", "api_key": key, "User-Agent": SCRAPER_USER_AGENT}
    # Counts against the configured daily / monthly call budget first.
    (before_request or (lambda: None))()
    try:
        response = session.post(PRLABS_JOBS_URL, json=payload, headers=headers,
                                timeout=max(SCRAPER_TIMEOUT_SECONDS, PRLABS_TIMEOUT_SECONDS))
    except requests.Timeout as exc:
        raise PRLabsAPIError("Timed out contacting the PR Labs Jobs API") from exc
    except requests.RequestException as exc:
        raise PRLabsAPIError(f"PR Labs request failed: {type(exc).__name__}") from exc

    if response.status_code in (401, 403):
        raise PRLabsAPIError("PR Labs rejected the API key (check PRLABS_API_KEY and remaining credits)")
    if response.status_code in (402, 429):
        raise PRLabsAPIError(f"PR Labs credits or rate limit exhausted (HTTP {response.status_code})")
    if response.status_code in (500, 502, 503, 504):
        raise PRLabsAPIError(f"PR Labs Jobs API temporarily unavailable (HTTP {response.status_code})")
    if response.status_code != 200:
        raise PRLabsAPIError(f"PR Labs returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise PRLabsAPIError("PR Labs response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise PRLabsAPIError("PR Labs response has an unexpected shape")
    if str(data.get("status", "True")).strip().lower() not in {"true", "1"}:
        reason = _text(data.get("message") or data.get("error") or data.get("detail"))[:160]
        raise PRLabsAPIError(f"PR Labs reported an error{': ' + reason if reason else ''}")

    jobs = []
    for item in data.get("jobs") or []:
        normalized = normalize_job(item)
        if normalized:
            jobs.append(normalized)
    logger.info("[Jobs][PRLabs] %r in %r -> %d job(s)", search_term, location, len(jobs))
    return jobs
