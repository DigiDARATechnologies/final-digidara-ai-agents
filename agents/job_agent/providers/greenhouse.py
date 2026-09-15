import logging
import re

import requests

from ..config import GREENHOUSE_MAX_RESPONSE_BYTES, SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT
from ..scraper import ScraperError, _iso_datetime, _text
from .config_loader import get_greenhouse_filters


logger = logging.getLogger(__name__)

GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"
BOARD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,100}$", re.IGNORECASE)
_MAX_PAGES = 20

_EMPLOYMENT_TYPE_KEYS = {"employment type", "job type", "employee type", "employment status"}

# Error categories a source's health can be classified into. `permanent`
# categories (board_not_found, invalid_configuration) mean retrying on the
# next scheduled run is pointless until someone fixes the underlying
# config, so the source is marked INVALID and excluded from automatic
# collection; everything else is a transient condition that may clear up
# on its own, so the source is marked TEMPORARILY_FAILED and retried next
# run. See service.process_run(), which reads `.category`/`.permanent`
# off any raised exception (duck-typed, not Greenhouse-specific) to update
# job_sources' lifecycle status.
CATEGORY_BOARD_NOT_FOUND = "board_not_found"
CATEGORY_FORBIDDEN = "forbidden"
CATEGORY_RATE_LIMITED = "rate_limited"
CATEGORY_SERVER_ERROR = "server_error"
CATEGORY_UNEXPECTED_RESPONSE = "unexpected_response"
CATEGORY_RESPONSE_SIZE_LIMIT = "response_size_limit"
CATEGORY_MALFORMED_RESPONSE = "malformed_response"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_NETWORK_ERROR = "network_error"
CATEGORY_INVALID_CONFIGURATION = "invalid_configuration"

PERMANENT_CATEGORIES = {CATEGORY_BOARD_NOT_FOUND, CATEGORY_INVALID_CONFIGURATION}


class GreenhouseAPIError(ScraperError):
    """Raised for any Greenhouse-board-specific failure (HTTP, network, parsing).

    Callers are expected to catch this per-company so one failing board
    does not abort collection for the remaining configured companies.
    `category` and `permanent` classify the failure for source-lifecycle
    tracking (see the CATEGORY_* constants above).
    """

    def __init__(self, message, status_code=None, category="unknown", permanent=False):
        super().__init__(message)
        self.status_code = status_code
        self.category = category
        self.permanent = permanent


def _validate_board_id(board_id):
    board_id = str(board_id or "").strip()
    if not BOARD_ID_PATTERN.match(board_id):
        raise GreenhouseAPIError(
            f"Invalid Greenhouse board id: {board_id!r}",
            category=CATEGORY_INVALID_CONFIGURATION,
            permanent=True,
        )
    return board_id


def _board_url(board_id, include_content=True):
    suffix = "?content=true" if include_content else ""
    return f"{GREENHOUSE_API_BASE}/{board_id}/jobs{suffix}"


def _request(session, url):
    headers = {"User-Agent": SCRAPER_USER_AGENT, "Accept": "application/json"}
    try:
        response = session.get(url, headers=headers, timeout=SCRAPER_TIMEOUT_SECONDS)
    except requests.Timeout as exc:
        raise GreenhouseAPIError(
            f"Timed out contacting Greenhouse ({url})", category=CATEGORY_TIMEOUT,
        ) from exc
    except requests.ConnectionError as exc:
        raise GreenhouseAPIError(
            f"Could not connect to Greenhouse ({url})", category=CATEGORY_NETWORK_ERROR,
        ) from exc
    except requests.RequestException as exc:
        raise GreenhouseAPIError(
            f"Greenhouse request failed ({url}): {exc}", category=CATEGORY_NETWORK_ERROR,
        ) from exc

    if response.status_code == 404:
        raise GreenhouseAPIError(
            f"Greenhouse board not found ({url})",
            status_code=404, category=CATEGORY_BOARD_NOT_FOUND, permanent=True,
        )
    if response.status_code == 403:
        # Distinct from 404: the board may genuinely exist but access is
        # being refused right now (bot/WAF protection, a temporarily
        # private board). Treated as transient, not a permanent
        # board-not-found - retried next run rather than marked INVALID.
        raise GreenhouseAPIError(
            f"Greenhouse forbade this request ({url})",
            status_code=403, category=CATEGORY_FORBIDDEN,
        )
    if response.status_code == 429:
        raise GreenhouseAPIError(
            f"Greenhouse rate-limited this request ({url})",
            status_code=429, category=CATEGORY_RATE_LIMITED,
        )
    if response.status_code >= 500:
        raise GreenhouseAPIError(
            f"Greenhouse returned a server error {response.status_code} ({url})",
            status_code=response.status_code, category=CATEGORY_SERVER_ERROR,
        )
    if response.status_code != 200:
        raise GreenhouseAPIError(
            f"Unexpected Greenhouse response {response.status_code} ({url})",
            status_code=response.status_code, category=CATEGORY_UNEXPECTED_RESPONSE,
        )

    content = getattr(response, "content", None)
    if content is not None and len(content) > GREENHOUSE_MAX_RESPONSE_BYTES:
        raise GreenhouseAPIError(
            f"Greenhouse response exceeded the configured size limit ({url})",
            category=CATEGORY_RESPONSE_SIZE_LIMIT,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise GreenhouseAPIError(
            f"Greenhouse returned malformed JSON ({url})", category=CATEGORY_MALFORMED_RESPONSE,
        ) from exc

    if not isinstance(payload, dict):
        raise GreenhouseAPIError(
            f"Unexpected Greenhouse response shape ({url})", category=CATEGORY_UNEXPECTED_RESPONSE,
        )
    return payload


def _next_page_url(payload):
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    next_url = meta.get("next_page") or meta.get("next")
    return str(next_url) if next_url else None


def _fetch_all_pages(session, board_id, include_content):
    jobs = []
    url = _board_url(board_id, include_content=include_content)
    seen_urls = set()
    for _ in range(_MAX_PAGES):
        payload = _request(session, url)
        jobs.extend(payload.get("jobs") or [])
        next_url = _next_page_url(payload)
        if not next_url or next_url in seen_urls:
            break
        seen_urls.add(next_url)
        url = next_url
    return jobs


def fetch_company_jobs(board_id, session=None):
    """Fetch every published job for one Greenhouse board.

    No API key is used or required: this calls Greenhouse's public Job
    Board API, the same endpoint Greenhouse documents for embedding a
    company's postings on a third-party site. `session` can be injected
    (e.g. a mock) for testing; a real `requests.Session()` is created
    otherwise.

    Requests full HTML descriptions (`content=true`) by default. A handful
    of very large boards exceed GREENHOUSE_MAX_RESPONSE_BYTES with
    descriptions included; rather than raising a global limit for every
    company (or dropping descriptions everywhere), this falls back once to
    the same board without `content=true` - a much smaller, metadata-only
    payload - so a single oversized board degrades gracefully (jobs with
    empty descriptions) instead of failing outright. Every other company
    is unaffected.
    """
    board_id = _validate_board_id(board_id)
    session = session or requests.Session()

    try:
        return _fetch_all_pages(session, board_id, include_content=True)
    except GreenhouseAPIError as exc:
        if exc.category != CATEGORY_RESPONSE_SIZE_LIMIT:
            raise
        logger.warning(
            "[Jobs][Greenhouse] Board '%s' exceeded the response size limit with full descriptions; "
            "retrying without content=true (descriptions will be empty for this board)",
            board_id,
        )
        return _fetch_all_pages(session, board_id, include_content=False)


def _employment_type(metadata):
    if not isinstance(metadata, list):
        return ""
    for field in metadata:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip().lower()
        if name in _EMPLOYMENT_TYPE_KEYS and field.get("value"):
            return _text(field.get("value"))
    return ""


def _work_mode(location_text):
    lowered = (location_text or "").lower()
    if "remote" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    return ""


def normalize_job(raw_job, company_name, board_id):
    """Map one raw Greenhouse job JSON object into the project's canonical job dict.

    Returns None (rather than raising) when Greenhouse is missing fields
    this platform treats as mandatory (id, title, application URL) — the
    caller skips such records instead of failing the whole board.
    """
    if not isinstance(raw_job, dict):
        return None

    source_job_id = str(raw_job.get("id") or "").strip()
    title = _text(raw_job.get("title"))
    apply_url = str(raw_job.get("absolute_url") or "").strip()
    if not source_job_id or not title or not apply_url:
        return None

    location = _text((raw_job.get("location") or {}).get("name"))
    if not location:
        offices = raw_job.get("offices") or []
        location = ", ".join(_text(office.get("name")) for office in offices if isinstance(office, dict) and office.get("name"))

    departments = raw_job.get("departments") or []
    department = ", ".join(
        _text(dept.get("name")) for dept in departments if isinstance(dept, dict) and dept.get("name")
    )

    return {
        "source": "greenhouse",
        "source_job_id": source_job_id,
        "external_id": source_job_id,
        "title": title,
        "company": company_name,
        "location": location,
        "department": department,
        "employment_type": _employment_type(raw_job.get("metadata")),
        "workplace_type": _work_mode(location),
        "work_mode": _work_mode(location),
        "salary_text": "",
        "description": _text(raw_job.get("content")),
        "skills": [],
        "job_url": apply_url,
        "application_url": apply_url,
        "apply_url": apply_url,
        "source_url": apply_url,
        "posted_at": _iso_datetime(raw_job.get("first_published") or raw_job.get("updated_at")),
        "published_at": _iso_datetime(raw_job.get("first_published") or raw_job.get("updated_at")),
        "updated_at": _iso_datetime(raw_job.get("updated_at")),
        "expires_at": None,
        "board_id": board_id,
    }


def _location_matches(location_text, keywords):
    if not keywords:
        return True
    lowered = (location_text or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _is_entry_level(title, exclude_keywords, entry_keywords):
    lowered = (title or "").lower()
    if any(keyword in lowered for keyword in entry_keywords):
        return True
    if any(keyword in lowered for keyword in exclude_keywords):
        return False
    return True


class NormalizedJobs(list):
    """A plain list of normalized jobs, with the raw (pre-filter) count attached.

    Behaves exactly like a list everywhere it's consumed (len(), iteration,
    indexing, `for job in scraped_jobs`) - `raw_count` is purely additional
    metadata so service.process_run() can tell a genuinely empty Greenhouse
    board (raw_count == 0) apart from a board whose jobs were all dropped
    by the location/seniority filters below (raw_count > 0, len() == 0).
    Other source types return a plain list; process_run() reads this via
    getattr with a fallback so it stays optional for them.
    """

    def __init__(self, jobs, raw_count):
        super().__init__(jobs)
        self.raw_count = raw_count


def fetch_and_normalize(board_id, company_name, session=None, filters=None):
    """Fetch, normalize, and filter one company's Greenhouse board in one call.

    This is the function the generic scraper dispatch (`scraper.scrape_source`)
    calls for `source_type == "greenhouse"`, keeping the existing
    fetch -> normalize -> dedupe/upsert -> database pipeline unchanged.

    Jobs outside the configured target locations, or that read as senior
    (unless the title also signals entry-level), are dropped here rather
    than stored as noise — see providers.yaml `greenhouse.filters`. The
    returned list's `.raw_count` preserves how many jobs Greenhouse itself
    published, before any of that filtering.
    """
    filters = filters if filters is not None else get_greenhouse_filters()
    raw_jobs = fetch_company_jobs(board_id, session=session)
    normalized = []
    skipped_invalid = 0
    skipped_location = 0
    skipped_seniority = 0
    for raw_job in raw_jobs:
        job = normalize_job(raw_job, company_name, board_id)
        if job is None:
            skipped_invalid += 1
            continue
        if not _location_matches(job["location"], filters["location_keywords"]):
            skipped_location += 1
            continue
        if filters["entry_level_only"] and not _is_entry_level(
            job["title"], filters["exclude_title_keywords"], filters["entry_title_keywords"]
        ):
            skipped_seniority += 1
            continue
        normalized.append(job)
    if skipped_invalid or skipped_location or skipped_seniority:
        logger.info(
            "[Jobs][Greenhouse] Board '%s': %d kept, %d invalid, %d outside target locations, %d filtered as senior-level",
            board_id, len(normalized), skipped_invalid, skipped_location, skipped_seniority,
        )
    return NormalizedJobs(normalized, raw_count=len(raw_jobs))
