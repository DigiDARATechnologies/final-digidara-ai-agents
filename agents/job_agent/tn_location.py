"""Tamil Nadu location engine — provider-independent per-job location classification.

Given a job's raw location text (whatever a provider's normalize step
produced — Greenhouse, Apify, a manual entry, or any future provider),
classifies:

  - district: the specific Tamil Nadu district matched, or None
  - region:   TAMIL_NADU / OTHER_INDIA / INTERNATIONAL / UNKNOWN
  - location_type: ONSITE / HYBRID / REMOTE / UNKNOWN

This module is deliberately generic (no Greenhouse-specific knowledge)
and intentionally NOT coupled to which company posted the job — a company
whose registry entry says "Coimbatore" can still post a Bangalore or
Remote job, and that job must classify accordingly, from its own location
text alone. See providers.yaml's comment on this same point.
"""

# Canonical Tamil Nadu district name -> alias/spelling variants that
# should resolve to it. Checked in this order, so a name that could be a
# substring of another (none currently) would resolve to the first
# listed. Includes the current Tamil Nadu districts plus the commonly searched
# Hosur city retained for backward compatibility with existing profiles.
TN_DISTRICTS = {
    "Chennai": ["chennai"],
    "Coimbatore": ["coimbatore"],
    "Madurai": ["madurai", "madhurai"],
    "Tiruchirappalli": ["tiruchirappalli", "tiruchirapalli", "trichy"],
    "Salem": ["salem"],
    "Tiruppur": ["tiruppur", "tirupur"],
    "Erode": ["erode"],
    "Vellore": ["vellore"],
    "Tirunelveli": ["tirunelveli"],
    "Thoothukudi": ["thoothukudi", "tuticorin"],
    "Thanjavur": ["thanjavur", "tanjore"],
    "Dindigul": ["dindigul"],
    "Hosur": ["hosur"],
    "Kanchipuram": ["kanchipuram", "kancheepuram"],
    "Chengalpattu": ["chengalpattu", "chengalpet"],
    "Ranipet": ["ranipet"],
    "Krishnagiri": ["krishnagiri"],
    "Namakkal": ["namakkal"],
    "Karur": ["karur"],
    "Cuddalore": ["cuddalore"],
    "Villupuram": ["villupuram", "viluppuram"],
    "Kallakurichi": ["kallakurichi"],
    "Nagapattinam": ["nagapattinam"],
    "Mayiladuthurai": ["mayiladuthurai"],
    "Tenkasi": ["tenkasi"],
    "Sivaganga": ["sivaganga", "sivagangai"],
    "Ramanathapuram": ["ramanathapuram"],
    "Virudhunagar": ["virudhunagar"],
    "Pudukkottai": ["pudukkottai", "pudukottai"],
    "Perambalur": ["perambalur"],
    "Ariyalur": ["ariyalur"],
    "The Nilgiris": ["nilgiris", "ooty", "udhagamandalam"],
    "Dharmapuri": ["dharmapuri"],
    "Kanyakumari": ["kanyakumari", "nagercoil"],
    "Theni": ["theni"],
    "Tiruvannamalai": ["tiruvannamalai", "thiruvannamalai"],
    "Tiruvarur": ["tiruvarur", "thiruvarur"],
    "Tirupattur": ["tirupattur", "thirupattur"],
    "Tiruvallur": ["tiruvallur", "thiruvallur"],
}

TAMIL_NADU_STATE_ALIASES = ["tamil nadu", "tamilnadu"]

# Common non-TN Indian metros/hubs. Used only to distinguish OTHER_INDIA
# from INTERNATIONAL/UNKNOWN when no TN district or state name matched —
# never used to produce a TAMIL_NADU classification.
OTHER_INDIA_HINTS = [
    "bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "delhi",
    "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad", "jaipur",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "ladakh",
    "chandigarh", "bhubaneswar", "indore", "lucknow", "india",
]

# User-facing canonical names. Work modes intentionally do not live in this
# map: "Remote" is a work mode, not a city, and must never be persisted as a
# physical location.
INDIA_LOCATION_ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "hyderabad": "Hyderabad",
    "hydrabad": "Hyderabad",
    "secunderabad": "Hyderabad",
    "pune": "Pune",
    "mumbai": "Mumbai",
    "navi mumbai": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "noida": "Noida",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "jaipur": "Jaipur",
    "kochi": "Kochi",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "thiruvananthapuram": "Thiruvananthapuram",
    "ladakh": "Ladakh",
    "chandigarh": "Chandigarh",
    "bhubaneswar": "Bhubaneswar",
    "indore": "Indore",
    "lucknow": "Lucknow",
}

INTERNATIONAL_HINTS = [
    "usa", "united states", "u.s.", "uk", "united kingdom", "canada",
    "germany", "singapore", "australia", "france", "netherlands", "spain",
    "ireland", "poland", "mexico", "brazil", "philippines", "vietnam",
    "japan", "china", "denmark", "sweden", "switzerland", "belgium",
]

REMOTE_KEYWORDS = ["remote"]
HYBRID_KEYWORDS = ["hybrid"]
ONSITE_KEYWORDS = ["onsite", "on-site", "in-office", "in office"]

REGION_TAMIL_NADU = "TAMIL_NADU"
REGION_OTHER_INDIA = "OTHER_INDIA"
REGION_INTERNATIONAL = "INTERNATIONAL"
REGION_UNKNOWN = "UNKNOWN"

TYPE_ONSITE = "ONSITE"
TYPE_HYBRID = "HYBRID"
TYPE_REMOTE = "REMOTE"
TYPE_UNKNOWN = "UNKNOWN"


def _padded(text):
    return f" {(text or '').lower()} "


def _contains_alias(text, alias):
    """Match a place as a token/phrase, never as part of another word."""
    import re

    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", (text or "").lower()))


def canonicalize_location(value):
    """Return a canonical known Indian location while preserving unknown input."""
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    for district, aliases in TN_DISTRICTS.items():
        if lowered == district.lower() or lowered in {alias.lower() for alias in aliases}:
            return district
    return INDIA_LOCATION_ALIASES.get(lowered, raw.title())


def extract_known_locations(text):
    """Extract supported physical locations from a user message."""
    positions = {}
    for district, aliases in TN_DISTRICTS.items():
        matches = [text.lower().find(alias.lower()) for alias in aliases if _contains_alias(text, alias)]
        if matches:
            positions[district] = min(matches)
    for alias, canonical in sorted(INDIA_LOCATION_ALIASES.items(), key=lambda item: -len(item[0])):
        if _contains_alias(text, alias):
            position = text.lower().find(alias.lower())
            positions[canonical] = min(position, positions.get(canonical, position))
    found = [value for value, _ in sorted(positions.items(), key=lambda item: item[1])]
    if not found:
        # Safe free-form fallback only when the user used an explicit location
        # construction. This supports portal cities outside the static alias
        # catalogue without interpreting arbitrary skills as locations.
        import re

        match = re.search(
            r"\b(?:jobs?|openings?|roles?)\s+(?:in|near|at)\s+([a-z][a-z .'-]{1,40})",
            text or "",
            re.IGNORECASE,
        )
        if match:
            candidate = re.split(r"\s+(?:for|with|as|using)\s+", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            candidate = candidate.strip(" .,-")
            if candidate and candidate.lower() not in {
                "remote", "hybrid", "onsite", "all", "anywhere",
                "my location", "my preferred location", "the preferred location",
                "preferred location", "saved location", "selected location",
            }:
                found.append(canonicalize_location(candidate))
    return found


def location_matches_preferences(job_location, work_mode, target_locations):
    """Match only a listing's stated location, without cross-city fallback.

    Remote listings match only an explicit Remote target. Unknown targets are
    matched literally so the filter remains useful beyond the alias catalogue.
    """
    targets = [str(item).strip() for item in (target_locations or []) if str(item).strip()]
    if not targets:
        return True
    if any(str(target).strip().lower() in {"any", "anywhere", "no preference", "either"} for target in targets):
        return True

    location = (job_location or "").strip()
    mode = (work_mode or "").strip().lower()
    is_remote = mode == "remote" or _contains_alias(location, "remote") or "work from home" in location.lower()

    for raw_target in targets:
        target_mode = raw_target.lower()
        if target_mode in {"remote", "work from home", "wfh", "hybrid", "onsite", "on-site", "office"}:
            expected_mode = "remote" if target_mode in {"remote", "work from home", "wfh"} else ("onsite" if target_mode == "office" else target_mode.replace("-", ""))
            normalized_mode = "onsite" if mode == "office" else mode.replace("-", "")
            if (expected_mode == "remote" and is_remote) or normalized_mode == expected_mode:
                return True
            continue

        canonical = canonicalize_location(raw_target)
        aliases = [canonical]
        for district, district_aliases in TN_DISTRICTS.items():
            if canonical == district:
                aliases.extend(district_aliases)
                break
        aliases.extend(alias for alias, value in INDIA_LOCATION_ALIASES.items() if value == canonical)
        if any(_contains_alias(location, alias) for alias in aliases):
            return True
    return False


def classify_district(location_text):
    """Return the matched canonical Tamil Nadu district name, or None."""
    padded = _padded(location_text)
    for district, aliases in TN_DISTRICTS.items():
        if any(alias in padded for alias in aliases):
            return district
    return None


def classify_location_type(location_text):
    """Return ONSITE / HYBRID / REMOTE / UNKNOWN from the location text.

    A specific place name with no explicit remote/hybrid wording is
    treated as ONSITE (Greenhouse's convention: a listed office location
    with no remote/hybrid tag means work happens there). Genuinely empty
    text is UNKNOWN rather than guessed.
    """
    padded = _padded(location_text)
    if any(keyword in padded for keyword in REMOTE_KEYWORDS):
        return TYPE_REMOTE
    if any(keyword in padded for keyword in HYBRID_KEYWORDS):
        return TYPE_HYBRID
    if any(keyword in padded for keyword in ONSITE_KEYWORDS):
        return TYPE_ONSITE
    if location_text and location_text.strip():
        return TYPE_ONSITE
    return TYPE_UNKNOWN


def classify_region(location_text, district=None):
    """Return TAMIL_NADU / OTHER_INDIA / INTERNATIONAL / UNKNOWN.

    A bare "Remote" with no place name attached deliberately resolves to
    UNKNOWN here, not TAMIL_NADU and not OTHER_INDIA — remote jobs are
    kept as their own case rather than assigned a region no evidence
    supports (see providers.yaml and the location engine tests).
    """
    if district:
        return REGION_TAMIL_NADU
    padded = _padded(location_text)
    if any(alias in padded for alias in TAMIL_NADU_STATE_ALIASES):
        return REGION_TAMIL_NADU
    if any(hint in padded for hint in INTERNATIONAL_HINTS):
        return REGION_INTERNATIONAL
    if any(hint in padded for hint in OTHER_INDIA_HINTS):
        return REGION_OTHER_INDIA
    return REGION_UNKNOWN


def classify_job_location(location_text):
    """Single entry point: returns (district, region, location_type) for one job."""
    district = classify_district(location_text)
    location_type = classify_location_type(location_text)
    region = classify_region(location_text, district)
    return district, region, location_type


ALL_TN_DISTRICTS = tuple(TN_DISTRICTS.keys())
