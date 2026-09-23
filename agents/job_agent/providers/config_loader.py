import logging
import os

import yaml


logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "providers.yaml")
CONFIG_PATH_ENV = "JOBS_PROVIDERS_CONFIG_PATH"


def _config_path():
    return os.getenv(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH)


def load_providers_config(path=None):
    """Load the providers YAML file into a plain dict.

    Missing files or malformed top-level content degrade to an empty
    config (all providers effectively disabled) rather than raising, so a
    misconfigured deployment does not take down the whole jobs module.
    """
    path = path or _config_path()
    if not os.path.exists(path):
        logger.warning("[Jobs][Providers] Config file not found at %s; providers disabled", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError:
        logger.exception("[Jobs][Providers] Failed to parse providers config at %s", path)
        return {}
    if not isinstance(data, dict):
        logger.warning("[Jobs][Providers] Providers config at %s must be a mapping; ignoring", path)
        return {}
    return data


_COMPANY_METADATA_FIELDS = ("district", "city", "state", "country", "category")


def _company_metadata(entry):
    return {field: entry.get(field) for field in _COMPANY_METADATA_FIELDS}


def get_greenhouse_companies(config=None):
    """Return the enabled Greenhouse companies as a list of company dicts.

    Each dict has `name`, `board_id`, and registry metadata (`district`,
    `city`, `state`, `country`, `category`) — informational about the
    company, not a per-job classification (see tn_location.py for that).

    Both the top-level `greenhouse.enabled` flag and each company's own
    `enabled` flag are honoured. An entry with `status: pending_validation`
    is excluded here regardless of its `enabled` flag — a candidate whose
    board or location hasn't been confirmed must never be synced as a
    live source by accident; see get_pending_validation_companies() to
    list those separately. Entries missing a name or board id are logged
    and skipped rather than raising, since a single bad row should not
    disable every configured company.
    """
    config = load_providers_config() if config is None else config
    greenhouse = config.get("greenhouse") or {}
    if not isinstance(greenhouse, dict) or not greenhouse.get("enabled"):
        return []

    companies = greenhouse.get("companies") or []
    if not isinstance(companies, list):
        logger.warning("[Jobs][Providers] greenhouse.companies must be a list; ignoring")
        return []

    result = []
    seen_board_ids = set()
    for entry in companies:
        if not isinstance(entry, dict):
            logger.warning("[Jobs][Providers] Skipping non-mapping Greenhouse company entry: %r", entry)
            continue
        if str(entry.get("status") or "").strip().lower() == "pending_validation":
            continue
        name = str(entry.get("name") or "").strip()
        board_id = str(entry.get("board_id") or "").strip()
        enabled = entry.get("enabled", True)
        if not name or not board_id:
            logger.warning(
                "[Jobs][Providers] Skipping Greenhouse company with missing name or board_id: %r", entry
            )
            continue
        if not enabled:
            continue
        if board_id in seen_board_ids:
            logger.warning("[Jobs][Providers] Duplicate Greenhouse board_id %r ignored", board_id)
            continue
        seen_board_ids.add(board_id)
        result.append({"name": name, "board_id": board_id, **_company_metadata(entry)})
    return result


def get_pending_validation_companies(config=None):
    """Return Greenhouse candidates marked `status: pending_validation`.

    These are deliberately never returned by get_greenhouse_companies()
    and never synced/collected automatically — they exist so the admin
    UI can list "known candidates awaiting confirmation" (board id
    resolves but location or company identity is unverified) without
    treating them as live sources. See providers.yaml for the current
    candidates and why each is pending.
    """
    config = load_providers_config() if config is None else config
    greenhouse = config.get("greenhouse") or {}
    companies = greenhouse.get("companies") or []
    if not isinstance(companies, list):
        return []

    result = []
    for entry in companies:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "").strip().lower() != "pending_validation":
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        result.append({
            "name": name,
            "board_id": str(entry.get("board_id") or "").strip() or None,
            "candidate_note": entry.get("candidate_note") or "",
            **_company_metadata(entry),
        })
    return result


DEFAULT_LOCATION_KEYWORDS = [
    "chennai", "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem",
    "tiruppur", "erode", "vellore", "tirunelveli", "thoothukudi", "thanjavur",
    "dindigul", "hosur", "kanchipuram", "chengalpattu", "tamil nadu",
    "tamilnadu", "bengaluru", "bangalore", "hyderabad",
]
DEFAULT_EXCLUDE_TITLE_KEYWORDS = [
    "senior", "sr.", "staff", "principal", "lead", "manager", "director",
    "head of", "vp", "vice president", "chief", "architect",
]
DEFAULT_ENTRY_TITLE_KEYWORDS = [
    "entry", "junior", "jr.", "associate", "graduate", "intern", "trainee",
    "fresher", "campus", "new grad", "early career",
]


def get_greenhouse_filters(config=None):
    """Read the location/seniority filters applied to every Greenhouse job.

    Falls back to the Tamil Nadu / Bengaluru / Hyderabad + entry-level
    defaults documented in providers.yaml when a list is missing or the
    wrong type, so a malformed filters block degrades to the safe default
    instead of disabling filtering entirely.
    """
    config = load_providers_config() if config is None else config
    greenhouse = config.get("greenhouse") or {}
    filters = greenhouse.get("filters") or {}
    if not isinstance(filters, dict):
        filters = {}

    def _string_list(value, default):
        if isinstance(value, list) and value:
            return [str(item).strip().lower() for item in value if str(item).strip()]
        return default

    return {
        "entry_level_only": bool(filters.get("entry_level_only", True)),
        "location_keywords": _string_list(filters.get("location_keywords"), list(DEFAULT_LOCATION_KEYWORDS)),
        "exclude_title_keywords": _string_list(
            filters.get("exclude_title_keywords"), list(DEFAULT_EXCLUDE_TITLE_KEYWORDS)
        ),
        "entry_title_keywords": _string_list(
            filters.get("entry_title_keywords"), list(DEFAULT_ENTRY_TITLE_KEYWORDS)
        ),
    }


def get_apify_config(config=None):
    """Return `{enabled, actors}` where each actor is a normalized
    `{platform, actor_id, enabled}` dict.

    Accepts either a bare actor-id string (legacy shape — `platform`
    defaults to the id itself) or the current `{platform, actor_id,
    enabled}` mapping documented in providers.yaml; an entry with no
    `actor_id` is skipped rather than raising, so one bad row (e.g.
    LinkedIn's still-empty actor_id) never disables the others.
    """
    config = load_providers_config() if config is None else config
    apify = config.get("apify") or {}
    if not isinstance(apify, dict):
        return {"enabled": False, "actors": []}

    raw_actors = apify.get("actors") or []
    actors = []
    if isinstance(raw_actors, list):
        for entry in raw_actors:
            if isinstance(entry, str):
                actor_id = entry.strip()
                if actor_id:
                    actors.append({"platform": actor_id, "actor_id": actor_id, "enabled": True})
            elif isinstance(entry, dict):
                platform = str(entry.get("platform") or "").strip()
                actor_id = str(entry.get("actor_id") or "").strip()
                # An environment override keeps provider credentials and
                # deploy-specific actor selection out of committed YAML. It
                # also lets the LinkedIn actor be changed without code edits.
                if platform:
                    actor_id = os.getenv(f"APIFY_{platform.upper()}_ACTOR_ID", "").strip() or actor_id
                if not actor_id:
                    continue
                platform = platform or actor_id
                run_input = entry.get("run_input")
                if run_input is not None and not isinstance(run_input, dict):
                    logger.warning("[Jobs][Providers] Skipping Apify actor '%s': run_input must be an object", platform)
                    continue
                actors.append({
                    "platform": platform,
                    "actor_id": actor_id,
                    "enabled": bool(entry.get("enabled", True)),
                    "run_input": run_input or {},
                })

    return {"enabled": bool(apify.get("enabled")), "actors": actors}


def get_apify_actor(platform, config=None):
    """Look up one configured actor by platform name, or None."""
    for actor in get_apify_config(config)["actors"]:
        if actor["platform"] == platform:
            return actor
    return None


DEFAULT_ADZUNA_QUERIES = [
    {"what": "Software Engineer", "where": "Chennai"},
    {"what": "Junior Developer", "where": "Tamil Nadu"},
    {"what": "Python Developer", "where": "Chennai"},
    {"what": "React Developer", "where": "Coimbatore"},
    {"what": "Web Developer", "where": "Madurai"},
    {"what": "Software Engineer", "where": "Bengaluru"},
    {"what": "Software Engineer", "where": "Hyderabad"},
]

DEFAULT_JSEARCH_QUERIES = [
    {"query": "Software Engineer Fresher in Chennai"},
    {"query": "Junior Developer in Tamil Nadu"},
    {"query": "Python Developer Fresher in Coimbatore"},
    {"query": "Software Engineer Fresher in Bengaluru"},
    {"query": "Junior Software Engineer in Hyderabad"},
]


def get_adzuna_config(config=None):
    """Return `{enabled, queries}` for Adzuna job search."""
    config = load_providers_config() if config is None else config
    adzuna = config.get("adzuna") or {}
    if not isinstance(adzuna, dict):
        return {"enabled": False, "queries": []}

    raw_queries = adzuna.get("queries")
    if isinstance(raw_queries, list) and raw_queries:
        queries = [
            {"what": str(q.get("what", "")).strip(), "where": str(q.get("where", "")).strip()}
            for q in raw_queries if isinstance(q, dict) and (q.get("what") or q.get("where"))
        ]
    else:
        queries = list(DEFAULT_ADZUNA_QUERIES)

    return {
        "enabled": bool(adzuna.get("enabled", True)),
        "queries": queries,
    }


def get_jsearch_config(config=None):
    """Return `{enabled, queries}` for RapidAPI JSearch."""
    config = load_providers_config() if config is None else config
    jsearch = config.get("jsearch") or {}
    if not isinstance(jsearch, dict):
        return {"enabled": False, "queries": []}

    raw_queries = jsearch.get("queries")
    if isinstance(raw_queries, list) and raw_queries:
        queries = []
        for q in raw_queries:
            if isinstance(q, str) and q.strip():
                queries.append({"query": q.strip()})
            elif isinstance(q, dict) and q.get("query"):
                queries.append({"query": str(q["query"]).strip()})
    else:
        queries = list(DEFAULT_JSEARCH_QUERIES)

    return {
        "enabled": bool(jsearch.get("enabled", True)),
        "queries": queries,
    }

