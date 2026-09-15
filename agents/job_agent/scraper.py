import hashlib
import html
import ipaddress
import json
import socket
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import SCRAPER_MAX_BYTES, SCRAPER_TIMEOUT_SECONDS, SCRAPER_USER_AGENT


class ScraperError(RuntimeError):
    pass


def _validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ScraperError("Only public HTTP(S) source URLs are supported")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ScraperError("Source hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ScraperError("Private or reserved source addresses are not allowed")
    return parsed


def _robots_allowed(session, source_url):
    parsed = urlparse(source_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = _request_public(session, robots_url)
        if response.status_code == 404:
            return True
        response.raise_for_status()
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return parser.can_fetch(SCRAPER_USER_AGENT, source_url)
    except requests.RequestException as exc:
        raise ScraperError(f"Could not verify robots.txt: {exc}") from exc


def _request_public(session, url, stream=False):
    current_url = url
    for _ in range(5):
        _validate_public_url(current_url)
        response = session.get(
            current_url,
            timeout=SCRAPER_TIMEOUT_SECONDS,
            stream=stream,
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ScraperError("Source returned a redirect without a destination")
            current_url = urljoin(current_url, location)
            continue
        return response
    raise ScraperError("Source exceeded the redirect limit")


def _fetch(session, url):
    _validate_public_url(url)
    if not _robots_allowed(session, url):
        raise ScraperError("robots.txt does not permit this scraper")
    response = _request_public(session, url, stream=True)
    response.raise_for_status()
    length = int(response.headers.get("Content-Length", "0") or 0)
    if length > SCRAPER_MAX_BYTES:
        raise ScraperError("Source response exceeds the configured size limit")
    chunks = []
    total = 0
    for chunk in response.iter_content(64 * 1024):
        total += len(chunk)
        if total > SCRAPER_MAX_BYTES:
            raise ScraperError("Source response exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks), response.encoding or "utf-8"


def _text(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or ""
    # Some sources (observed on at least one Greenhouse board) return
    # description text that is itself HTML-entity-encoded (e.g. "&lt;div&gt;"
    # instead of "<div>"), so a single BeautifulSoup pass sees inert text,
    # not real tags, and leaves the escaped markup in the output. Unescaping
    # first normalizes both cases; it is a no-op for plain text or normal HTML.
    unescaped = html.unescape(str(value))
    return BeautifulSoup(unescaped, "html.parser").get_text(" ", strip=True)


def _iso_datetime(value):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return None


def _location(value):
    if isinstance(value, list):
        return ", ".join(filter(None, (_location(item) for item in value)))
    if not isinstance(value, dict):
        return _text(value)
    address = value.get("address", value)
    if isinstance(address, dict):
        parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
        return ", ".join(_text(part) for part in parts if part)
    return _text(address)


def _job_from_json_ld(item, page_url):
    company = item.get("hiringOrganization") or {}
    identifier = item.get("identifier") or {}
    external_id = identifier.get("value") if isinstance(identifier, dict) else identifier
    apply_url = item.get("url") or page_url
    title = _text(item.get("title"))
    company_name = _text(company.get("name") if isinstance(company, dict) else company)
    if not title or not company_name or not apply_url:
        return None
    external_id = str(external_id or hashlib.sha256(f"{title}|{company_name}|{apply_url}".encode()).hexdigest()[:32])
    skills = item.get("skills") or item.get("qualifications") or ""
    return {
        "external_id": external_id,
        "title": title,
        "company": company_name,
        "location": _location(item.get("jobLocation")),
        "work_mode": "remote" if item.get("jobLocationType") == "TELECOMMUTE" else "onsite",
        "employment_type": _text(item.get("employmentType")),
        "salary_text": _text(item.get("baseSalary")),
        "description": _text(item.get("description")),
        "skills": [part.strip() for part in str(skills).replace(";", ",").split(",") if part.strip()],
        "apply_url": urljoin(page_url, str(apply_url)),
        "source_url": page_url,
        "published_at": _iso_datetime(item.get("datePosted")),
        "expires_at": _iso_datetime(item.get("validThrough")),
    }


def _walk_json_ld(value):
    if isinstance(value, list):
        for item in value:
            yield from _walk_json_ld(item)
    elif isinstance(value, dict):
        if value.get("@type") == "JobPosting" or "JobPosting" in (value.get("@type") or []):
            yield value
        for key in ("@graph", "itemListElement"):
            if key in value:
                yield from _walk_json_ld(value[key])


def _parse_json_ld(content, page_url):
    soup = BeautifulSoup(content, "html.parser")
    jobs = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        for item in _walk_json_ld(data):
            job = _job_from_json_ld(item, page_url)
            if job:
                jobs.append(job)
    return jobs


def _field(card, config, name, page_url):
    field = config.get(name)
    if not field:
        return ""
    if isinstance(field, str):
        field = {"selector": field}
    element = card.select_one(field.get("selector", ""))
    if not element:
        return ""
    attribute = field.get("attribute")
    value = element.get(attribute, "") if attribute else element.get_text(" ", strip=True)
    return urljoin(page_url, value) if field.get("url") else value


def _parse_html_cards(content, page_url, config):
    selector = config.get("item_selector")
    fields = config.get("fields") or {}
    if not selector or not fields:
        raise ScraperError("HTML-card sources require item_selector and fields configuration")
    soup = BeautifulSoup(content, "html.parser")
    jobs = []
    for card in soup.select(selector):
        title = _field(card, fields, "title", page_url)
        company = _field(card, fields, "company", page_url)
        apply_url = _field(card, fields, "apply_url", page_url)
        if not title or not company or not apply_url:
            continue
        external_id = _field(card, fields, "external_id", page_url)
        if not external_id:
            external_id = hashlib.sha256(f"{title}|{company}|{apply_url}".encode()).hexdigest()[:32]
        skills = _field(card, fields, "skills", page_url)
        jobs.append({
            "external_id": external_id,
            "title": title,
            "company": company,
            "location": _field(card, fields, "location", page_url),
            "work_mode": _field(card, fields, "work_mode", page_url),
            "employment_type": _field(card, fields, "employment_type", page_url),
            "description": _field(card, fields, "description", page_url),
            "skills": [part.strip() for part in skills.replace(";", ",").split(",") if part.strip()],
            "apply_url": apply_url,
            "source_url": page_url,
            "published_at": _iso_datetime(_field(card, fields, "published_at", page_url)),
            "expires_at": _iso_datetime(_field(card, fields, "expires_at", page_url)),
        })
    return jobs


def _parse_rss(content, page_url, config):
    parsed = feedparser.parse(content)
    default_company = config.get("default_company", "Unknown employer")
    jobs = []
    for entry in parsed.entries:
        title = _text(entry.get("title"))
        apply_url = entry.get("link")
        if not title or not apply_url:
            continue
        external_id = str(entry.get("id") or hashlib.sha256(apply_url.encode()).hexdigest()[:32])
        jobs.append({
            "external_id": external_id,
            "title": title,
            "company": _text(entry.get("author") or default_company),
            "location": _text(entry.get("location", "")),
            "work_mode": "",
            "employment_type": "",
            "description": _text(entry.get("summary") or entry.get("description")),
            "skills": [],
            "apply_url": urljoin(page_url, apply_url),
            "source_url": page_url,
            "published_at": _iso_datetime(entry.get("published")),
            "expires_at": None,
        })
    return jobs


def scrape_source(source):
    if not source.get("scraping_authorized"):
        raise ScraperError("Source is not marked as authorized for collection")
    if not source.get("is_active"):
        raise ScraperError("Source is disabled")

    try:
        config = json.loads(source.get("parser_config") or "{}")
    except ValueError as exc:
        raise ScraperError("Parser configuration is not valid JSON") from exc

    source_type = source["source_type"]

    # Greenhouse's public Job Board API is a fixed, trusted JSON endpoint
    # (not an arbitrary admin-entered URL), so it is fetched directly by
    # its own provider module rather than through the generic HTML/RSS
    # fetch pipeline below, which validates and parses page content.
    if source_type == "greenhouse":
        from .providers.greenhouse import fetch_and_normalize

        board_id = config.get("board_id") or ""
        company_name = config.get("company_name") or source.get("name") or ""
        return fetch_and_normalize(board_id, company_name)

    if source_type == "apify":
        from .providers.apify import fetch_and_normalize as apify_fetch_and_normalize

        actor_id = config.get("actor_id") or ""
        platform = config.get("platform") or actor_id
        run_input = config.get("run_input")
        if run_input is not None and not isinstance(run_input, dict):
            raise ScraperError("Apify parser_config.run_input must be an object")
        return apify_fetch_and_normalize(actor_id, platform=platform, run_input=run_input)

    session = requests.Session()
    session.headers.update({"User-Agent": SCRAPER_USER_AGENT, "Accept": "text/html, application/rss+xml, application/xml"})
    content_bytes, encoding = _fetch(session, source["source_url"])
    content = content_bytes.decode(encoding, errors="replace")

    if source_type == "json_ld":
        return _parse_json_ld(content, source["source_url"])
    if source_type == "html_cards":
        return _parse_html_cards(content, source["source_url"], config)
    if source_type == "rss":
        return _parse_rss(content_bytes, source["source_url"], config)
    raise ScraperError(f"Unsupported source type: {source_type}")
