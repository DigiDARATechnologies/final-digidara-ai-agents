import hashlib
import logging
import os
import requests

from ..config import SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT
from ..scraper import ScraperError, _iso_datetime, _text

logger = logging.getLogger(__name__)

JSEARCH_API_BASE = "https://jsearch.p.rapidapi.com/search-v2"
JSEARCH_API_FALLBACK = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"
RAPIDAPI_KEY_ENV = "RAPIDAPI_KEY"


def _make_external_id(source_job_id):
    if len(source_job_id) <= 240:
        return f"jsearch:{source_job_id}"
    digest = hashlib.sha256(source_job_id.encode("utf-8")).hexdigest()
    return f"jsearch:{source_job_id[:180]}_{digest[:32]}"


class JSearchNotConfigured(ScraperError):
    pass


class JSearchAPIError(ScraperError):
    pass


def is_configured():
    return bool(os.getenv(RAPIDAPI_KEY_ENV, "").strip())


def _token():
    token = os.getenv(RAPIDAPI_KEY_ENV, "").strip()
    if not token:
        raise JSearchNotConfigured(
            f"{RAPIDAPI_KEY_ENV} is not set; JSearch collection is skipped until key is configured"
        )
    return token


def _salary_text(raw_job):
    min_sal = raw_job.get("job_min_salary")
    max_sal = raw_job.get("job_max_salary")
    currency = raw_job.get("job_salary_currency") or "\u20b9"
    if min_sal and max_sal:
        return f"{currency} {int(min_sal):,} - {currency} {int(max_sal):,}"
    if min_sal:
        return f"From {currency} {int(min_sal):,}"
    if max_sal:
        return f"Up to {currency} {int(max_sal):,}"
    return ""


def normalize_job(raw_job):
    """Normalize one raw JSearch item into the canonical DigiDARA job dictionary."""
    if not isinstance(raw_job, dict):
        return None

    job_id = raw_job.get("job_id")
    title = _text(raw_job.get("job_title"))
    apply_url = str(raw_job.get("job_apply_link") or raw_job.get("job_google_link") or "").strip()
    if not apply_url and isinstance(raw_job.get("apply_options"), list) and raw_job["apply_options"]:
        apply_url = str(raw_job["apply_options"][0].get("apply_link") or "").strip()

    if not job_id or not title or not apply_url:
        return None

    source_job_id = str(job_id).strip()
    company = _text(raw_job.get("employer_name") or "Unknown Company")

    city = raw_job.get("job_city") or ""
    state = raw_job.get("job_state") or ""
    country = raw_job.get("job_country") or ""
    location_parts = [p for p in [city, state, country] if p]
    location = ", ".join(location_parts) if location_parts else _text(raw_job.get("job_location") or "")

    is_remote = raw_job.get("job_is_remote")
    work_mode = "remote" if is_remote else "onsite"

    skills = raw_job.get("job_required_skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    description = _text(raw_job.get("job_description") or "")
    published_at = _iso_datetime(raw_job.get("job_posted_at_datetime_utc") or raw_job.get("job_posted_at_timestamp"))

    return {
        "source": "jsearch",
        "source_job_id": source_job_id,
        "external_id": _make_external_id(source_job_id),
        "title": title,
        "company": company,
        "location": location,
        "work_mode": work_mode,
        "employment_type": _text(raw_job.get("job_employment_type") or "Full Time"),
        "salary_text": _salary_text(raw_job),
        "description": description,
        "skills": skills,
        "apply_url": apply_url,
        "source_url": apply_url,
        "published_at": published_at,
        "expires_at": None,
    }


def fetch_and_normalize(query, page=1, num_pages=1, date_posted="all", session=None):
    """Search Google Jobs / LinkedIn / Indeed via RapidAPI JSearch."""
    token = _token()
    session = session or requests.Session()

    params = {
        "query": query,
        "page": str(page),
        "num_pages": str(num_pages),
        "date_posted": date_posted,
    }
    headers = {
        "X-RapidAPI-Key": token,
        "X-RapidAPI-Host": JSEARCH_HOST,
        "User-Agent": SCRAPER_USER_AGENT,
    }

    timeout_seconds = max(SCRAPER_TIMEOUT_SECONDS * 2, 30)
    try:
        response = session.get(JSEARCH_API_BASE, params=params, headers=headers, timeout=timeout_seconds)
        if response.status_code == 404:
            # Try legacy endpoint only if search-v2 returned 404
            response = session.get(JSEARCH_API_FALLBACK, params=params, headers=headers, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise JSearchAPIError(f"Timed out contacting RapidAPI JSearch ({JSEARCH_API_BASE})") from exc
    except requests.RequestException as exc:
        raise JSearchAPIError(f"JSearch request failed: {exc}") from exc

    if response.status_code == 403 or response.status_code == 401:
        raise JSearchAPIError("JSearch API Key is invalid or unauthenticated")
    if response.status_code == 404:
        raise JSearchAPIError("JSearch subscription inactive or endpoint not found on RapidAPI")
    if response.status_code in (502, 503, 504):
        raise JSearchAPIError(f"RapidAPI JSearch gateway temporarily unavailable (HTTP {response.status_code})")
    if response.status_code != 200:
        raise JSearchAPIError(f"JSearch returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        data = response.json()
    except ValueError as exc:
        raise JSearchAPIError("JSearch response is not valid JSON") from exc

    raw_data = data.get("data")
    if isinstance(raw_data, dict):
        raw_items = raw_data.get("jobs") or []
    elif isinstance(raw_data, list):
        raw_items = raw_data
    else:
        raw_items = []

    jobs = []
    for item in raw_items:
        normalized = normalize_job(item)
        if normalized:
            jobs.append(normalized)

    return jobs
