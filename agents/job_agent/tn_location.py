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
# listed. All 32 Tamil Nadu districts per the current administrative list.
TN_DISTRICTS = {
    "Chennai": ["chennai"],
    "Coimbatore": ["coimbatore"],
    "Madurai": ["madurai"],
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
}

TAMIL_NADU_STATE_ALIASES = ["tamil nadu", "tamilnadu"]

# Common non-TN Indian metros/hubs. Used only to distinguish OTHER_INDIA
# from INTERNATIONAL/UNKNOWN when no TN district or state name matched —
# never used to produce a TAMIL_NADU classification.
OTHER_INDIA_HINTS = [
    "bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "delhi",
    "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad", "jaipur",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "india",
]

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
