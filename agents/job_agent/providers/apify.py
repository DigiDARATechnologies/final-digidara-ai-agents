"""Apify-backed job providers.

Not part of Greenhouse Milestone 1. This module exists so an Apify-backed
job source can be wired in later purely by:

  1. Setting the APIFY_API_TOKEN environment variable.
  2. Enabling `apify.enabled` and listing at least one actor under
     `apify.actors` in providers.yaml.
  3. Providing a verified `normalize_job()` mapping for the actor's specific
     dataset shape. LinkedIn is implemented; other actors remain guarded
     until their live output is verified.

Until all three are done, `run_apify_collection()` (see sync.py) is a
safe no-op: it logs why it is skipping and returns without touching the
database or making any network call. No API key is required or invented
here — the token always comes from the environment, never from a config
file, so it is never committed to source control.
"""

import logging
import os
from datetime import datetime
from urllib.parse import quote

import requests

from ..config import SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT


logger = logging.getLogger(__name__)

APIFY_API_BASE = "https://api.apify.com/v2"
APIFY_API_TOKEN_ENV = "APIFY_API_TOKEN"


class ApifyNotConfigured(RuntimeError):
    pass


class ApifyAPIError(RuntimeError):
    pass


def is_configured():
    return bool(os.getenv(APIFY_API_TOKEN_ENV, "").strip())


def _token():
    token = os.getenv(APIFY_API_TOKEN_ENV, "").strip()
    if not token:
        raise ApifyNotConfigured(
            f"{APIFY_API_TOKEN_ENV} is not set; Apify collection is skipped until a token is configured"
        )
    return token


def run_actor_and_fetch_items(actor_id, run_input=None, session=None):
    """Run an Apify actor synchronously and return its raw dataset items.

    This talks to Apify's real REST API (run-sync-get-dataset-items) and
    will work as soon as a token is set — but the returned items are
    actor-specific raw dicts, not yet canonical jobs. See normalize_job().
    """
    token = _token()
    session = session or requests.Session()
    # Apify's human-facing actor notation is `owner/actor`, while its REST
    # endpoint uses the API id `owner~actor`. Quote after conversion so a
    # configured identifier can never alter the request path.
    api_actor_id = quote(actor_id.replace("/", "~", 1), safe="~")
    url = f"{APIFY_API_BASE}/acts/{api_actor_id}/run-sync-get-dataset-items"
    headers = {"User-Agent": SCRAPER_USER_AGENT, "Content-Type": "application/json"}
    try:
        response = session.post(
            url,
            params={"token": token},
            json=run_input or {},
            headers=headers,
            timeout=SCRAPER_TIMEOUT_SECONDS * 3,
        )
    except requests.Timeout as exc:
        raise ApifyAPIError(f"Timed out running Apify actor '{actor_id}'") from exc
    except requests.ConnectionError as exc:
        raise ApifyAPIError(f"Could not connect to Apify for actor '{actor_id}'") from exc
    except requests.RequestException as exc:
        raise ApifyAPIError(f"Apify request failed for actor '{actor_id}': {exc}") from exc

    if response.status_code == 401:
        raise ApifyAPIError("Apify rejected the configured API token")
    if response.status_code >= 400:
        raise ApifyAPIError(f"Apify actor '{actor_id}' returned HTTP {response.status_code}")

    try:
        items = response.json()
    except ValueError as exc:
        raise ApifyAPIError(f"Apify returned malformed JSON for actor '{actor_id}'") from exc
    return items if isinstance(items, list) else []


def get_apify_status(apify_config):
    """Report whether Apify collection can actually run right now.

    Used by the worker CLI and the admin trigger route to explain a
    skipped run instead of silently doing nothing or raising.
    """
    if not apify_config.get("enabled"):
        return {"ready": False, "reason": "apify.enabled is false in providers.yaml"}
    if not is_configured():
        return {"ready": False, "reason": f"{APIFY_API_TOKEN_ENV} environment variable is not set"}
    if not [actor for actor in apify_config.get("actors", []) if actor.get("enabled")]:
        return {"ready": False, "reason": "no enabled actors configured under apify.actors in providers.yaml"}
    return {"ready": True, "reason": ""}


def _first(raw_item, *keys):
    """First non-empty value across several candidate field names."""
    for key in keys:
        value = raw_item.get(key)
        if value not in (None, "", []):
            return value
    return None


def _normalize_generic_job(raw_item, source_name, *, extra_title=(), extra_company=(), extra_url=(),
                            extra_id=(), extra_location=(), extra_description=(), extra_skills=(),
                            extra_salary=(), extra_posted=()):
    """Shared best-effort field-guessing body every per-platform normalizer
    below delegates to.

    UNVERIFIED against a real run of ANY of these actors — none of their
    exact dataset shapes have been confirmed, so every field tries several
    plausible candidate keys (a platform's own likely names first, via
    `extra_*`, then the common fallbacks below) and simply omits what it
    can't find, rather than guessing a single name with false confidence.
    After a platform's first "Run now" click in the admin panel, check its
    row in job_ingestion_runs (fetched vs. rejected counts) and
    job_sources.last_error, and tighten that platform's `extra_*` list in
    _NORMALIZERS below to match what actually came back.
    """
    title = _first(raw_item, *extra_title, "title", "jobTitle", "job_title", "position")
    company = _first(raw_item, *extra_company, "companyName", "company_name", "company", "employerName")
    apply_url = _first(raw_item, *extra_url, "jdURL", "jdUrl", "jobUrl", "job_url", "url", "link", "applyUrl")
    if not title or not company or not apply_url:
        return None

    external_id = _first(raw_item, *extra_id, "jobId", "job_id", "id") or apply_url
    location = _first(raw_item, *extra_location, "location", "jobLocation", "placeholders") or ""
    if isinstance(location, list):
        location = ", ".join(str(item) for item in location if item)
    description = _first(raw_item, *extra_description, "jobDescription", "description", "jd") or ""
    skills_raw = _first(raw_item, *extra_skills, "skills", "tagsAndSkills", "keySkills") or []
    if isinstance(skills_raw, str):
        skills = [item.strip() for item in skills_raw.split(",") if item.strip()]
    elif isinstance(skills_raw, list):
        skills = [str(item).strip() for item in skills_raw if str(item).strip()]
    else:
        skills = []
    posted_at = _first(raw_item, *extra_posted, "postedDate", "createdDate", "postDate", "datePosted")

    return {
        "source": source_name,
        "external_id": str(external_id),
        "title": str(title).strip(),
        "company": str(company).strip(),
        "location": str(location).strip(),
        "department": "",
        "employment_type": "",
        "work_mode": "",
        "salary_text": str(_first(raw_item, *extra_salary, "salary", "salaryText") or ""),
        "description": str(description),
        "skills": skills,
        "apply_url": str(apply_url).strip(),
        "source_url": str(apply_url).strip(),
        "published_at": posted_at,
    }


def _normalize_naukri_job(raw_item):
    """`crawloop/naukri-jobs-scraper` — see _normalize_generic_job()'s UNVERIFIED note."""
    return _normalize_generic_job(raw_item, "naukri")


def _normalize_foundit_job(raw_item):
    """`crawloop/foundit-jobs-scraper` — same author as Naukri's actor, same UNVERIFIED note."""
    return _normalize_generic_job(raw_item, "foundit")


def _normalize_hirist_job(raw_item):
    """`crawloop/hirist-jobs-scraper` — same author as Naukri's actor, same UNVERIFIED note."""
    return _normalize_generic_job(raw_item, "hirist")


def _normalize_instahyre_job(raw_item):
    """`parsebird/instahyre-jobs-scraper` — different actor author than the
    crawloop-based platforms above, so its field names may diverge more;
    same UNVERIFIED note applies."""
    return _normalize_generic_job(raw_item, "instahyre", extra_company=("employer",), extra_url=("profile_url",))


def _normalize_internshala_job(raw_item):
    """`hipersoft/internshala-scraper` — internship listings use "stipend"
    rather than "salary" and are often titled as the internship itself;
    same UNVERIFIED note applies otherwise."""
    return _normalize_generic_job(
        raw_item, "internshala", extra_title=("internship_name",), extra_salary=("stipend",),
    )


def _normalize_indeed_job(raw_item):
    """`solidscrape/indeed-jobs-scraper` — same UNVERIFIED note applies."""
    return _normalize_generic_job(raw_item, "indeed", extra_url=("job_link", "viewJobLink"))


def _normalize_glassdoor_job(raw_item):
    """`simpleapi/glassdoor-jobs-scraper` — same UNVERIFIED note applies."""
    return _normalize_generic_job(raw_item, "glassdoor", extra_company=("employer",))


def _normalize_linkedin_job(raw_item):
    """Map artificially/linkedin-jobs-scraper's documented output shape."""
    job = _normalize_generic_job(
        raw_item,
        "linkedin",
        extra_url=("jobUrl",),
        extra_posted=("listingDateParsed",),
    )
    if not job:
        return None
    posted_at = job.get("published_at")
    if isinstance(posted_at, str):
        try:
            # MySQL DATETIME does not consistently accept ISO timestamps
            # with a trailing Z, so store a timezone-naive UTC value.
            job["published_at"] = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return job


# Maps a providers.yaml `platform` name to its actor-specific field mapping.
# Add one entry here per platform once its actor's real output shape is
# confirmed — see get_apify_actor() in config_loader.py for how `platform`
# reaches this from the admin "Run now" button.
_NORMALIZERS = {
    "naukri": _normalize_naukri_job,
    "foundit": _normalize_foundit_job,
    "hirist": _normalize_hirist_job,
    "instahyre": _normalize_instahyre_job,
    "internshala": _normalize_internshala_job,
    "indeed": _normalize_indeed_job,
    "glassdoor": _normalize_glassdoor_job,
    "linkedin": _normalize_linkedin_job,
}


def normalize_job(raw_item, platform, company_hint=None):
    """Map one Apify dataset item into the canonical job dict.

    Dispatches on `platform` (providers.yaml's dispatch key, not the raw
    actor id) so each job board's actor gets its own field mapping. A
    platform with no entry in _NORMALIZERS yet (e.g. LinkedIn, pending an
    actor id and a sample item) raises clearly instead of guessing.
    """
    normalizer = _NORMALIZERS.get(platform)
    if normalizer is None:
        raise NotImplementedError(
            f"Apify normalize_job() has no field mapping for platform '{platform}' yet — "
            "add one to providers/apify.py's _NORMALIZERS once its actor's real output shape is known."
        )
    return normalizer(raw_item)


def fetch_and_normalize(actor_id, platform=None, run_input=None, session=None):
    """Fetch one actor's dataset and normalize it, mirroring the Greenhouse provider.

    This is what `scraper.scrape_source()` calls for `source_type == "apify"`,
    reusing the same fetch -> normalize -> dedupe/upsert -> database
    pipeline. It will raise `NotImplementedError` from `normalize_job()`
    for any platform with no mapping yet — that exception is caught by the
    existing `service.process_run()` error handling, so it surfaces as a
    normal failed run with a clear message rather than crashing collection.
    """
    items = run_actor_and_fetch_items(actor_id, run_input=run_input, session=session)
    normalized = []
    for item in items:
        job = normalize_job(item, platform or actor_id, company_hint=None)
        if job:
            normalized.append(job)
    return normalized
