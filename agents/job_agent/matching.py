import json
import math
import re
from typing import Any, Dict, List, Tuple

from .categories import OTHER_CATEGORY, categorize_course_name, categorize_job, category_labels, related_category_ids


STOP_WORDS = {
    "and", "the", "for", "with", "from", "course", "final", "exam",
    "developer", "engineer", "specialist", "associate", "junior", "senior",
}

ENTRY_KEYWORDS = [
    "fresher", "intern", "internship", "trainee", "graduate", "entry level", "entry-level",
    "junior", "jr.", "jr ", "associate", "campus", "new grad", "early career", "apprentice",
]

SENIOR_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager", "director", "head of",
    "vp", "vice president", "avp", "chief", "architect", "expert", "specialist iii", "iii", "iv",
]


def parse_list(value):
    if not value:
        return []
    if isinstance(value, list):
        values = value
    else:
        try:
            parsed = json.loads(value)
            values = parsed if isinstance(parsed, list) else [value]
        except (TypeError, ValueError):
            values = re.split(r"[,;\n]", str(value))
    return [str(item).strip() for item in values if str(item).strip()]


def _tokens(values):
    text = " ".join(values).lower()
    return {
        token for token in re.findall(r"[a-z0-9+#.]{2,}", text)
        if token not in STOP_WORDS
    }


def _matches_preference(text: str, preferences: list[str]) -> bool:
    """Check if any preference matches within text using word-boundary matching to
    prevent false-positive substring matches (e.g. 'it' inside 'security' or 'in' inside 'chennai')."""
    if not text or not preferences:
        return False
    text_lower = text.lower()
    for pref in preferences:
        pref = pref.strip().lower()
        if not pref:
            continue
        escaped_pref = re.escape(pref)
        if re.search(r"(?:\b|_)" + escaped_pref + r"(?:\b|_)", text_lower):
            return True
    return False


def classify_job_seniority(job: Dict[str, Any]) -> str:
    """
    Classifies a job into:
    - 'entry': Fresher, Intern, Junior, Trainee, Graduate (0-2 years)
    - 'growth': Mid-level, next-step role (2-4 years)
    - 'senior': Senior, Lead, AVP, Manager, 5+ years
    """
    title = str(job.get("title") or "").lower()
    desc = str(job.get("description") or "").lower()[:400]
    exp_min = job.get("experience_min")
    exp_max = job.get("experience_max")

    # Check explicit title keywords
    is_entry_title = any(re.search(r"\b" + re.escape(k) + r"\b", title) for k in ENTRY_KEYWORDS)
    is_senior_title = any(re.search(r"\b" + re.escape(k) + r"\b", title) for k in SENIOR_KEYWORDS)

    # Check 5+ years regex in title (e.g. "5.1-7 years")
    match_years = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to|\+)\s*(?:\d+(?:\.\d+)?)?\s*years?", title)
    if match_years:
        try:
            yrs = float(match_years.group(1))
            if yrs >= 4.0:
                return "senior"
            if yrs <= 2.0:
                return "entry"
            return "growth"
        except ValueError:
            pass

    if is_entry_title and not is_senior_title:
        return "entry"
    if is_senior_title:
        return "senior"

    # Inspect experience min/max if numeric
    if exp_min is not None:
        try:
            e_min = float(exp_min)
            if e_min >= 5.0:
                return "senior"
            if e_min <= 1.0:
                return "entry"
            if e_min <= 3.0:
                return "growth"
        except (ValueError, TypeError):
            pass

    # Default general tech postings with plain titles ("Software Engineer", "Web Developer")
    # without senior keywords are suitable for entry/growth
    return "entry"


def score_job(job: Dict[str, Any], profile: Dict[str, Any], course_name: str) -> Tuple[int, List[str]]:
    raw_job_skills = parse_list(job.get("skills"))
    if not raw_job_skills:
        from .skills import extract_skills_from_job
        raw_job_skills = extract_skills_from_job(job)
        job["skills"] = raw_job_skills

    job_skills = _tokens(raw_job_skills)
    student_skills = _tokens(parse_list(profile.get("skills")))
    course_skills = _tokens([course_name or ""])
    title_preferences = [item.lower() for item in parse_list(profile.get("preferred_titles"))]
    location_preferences = [item.lower() for item in parse_list(profile.get("preferred_locations"))]

    verified_overlap = job_skills & course_skills
    declared_overlap = job_skills & student_skills
    required_count = max(1, len(job_skills))

    # Rebalanced scoring: candidate's declared skills carry primary weight (35 pts)
    # over title keyword tokens (25 pts), summing cleanly to 100 max.
    if job_skills:
        skill_score = min(35, round(35 * len(declared_overlap) / required_count))
        verified_score = min(25, round(25 * len(verified_overlap) / required_count))
    else:
        verified_score = 0
        skill_score = 15 if declared_overlap or student_skills else 0

    title = (job.get("title") or "").lower()
    title_score = 10 if _matches_preference(title, title_preferences) else 0

    location = (job.get("location") or "").lower()
    location_score = 0
    if not location_preferences:
        location_score = 5
    elif _matches_preference(location, location_preferences):
        location_score = 10

    preferred_mode = (profile.get("preferred_work_mode") or "").lower()
    job_mode = (job.get("work_mode") or "").lower()
    mode_score = 5 if preferred_mode and preferred_mode == job_mode else (3 if not preferred_mode else 0)

    experience = float(profile.get("experience_years") or 0)
    seniority = classify_job_seniority(job)
    job["seniority_tier"] = seniority

    # Experience & Seniority alignment for college students/freshers (experience <= 1 year)
    seniority_modifier = 0
    if experience <= 1.0:
        if seniority == "entry":
            seniority_modifier = 15  # Strong boost for fresher/intern/entry roles
        elif seniority == "growth":
            seniority_modifier = 5   # Moderate fit for ambitious next-step roles
        elif seniority == "senior":
            seniority_modifier = -40  # Heavy penalty for 5+ yr / Senior / AVP roles
    else:
        # User has experience
        minimum = job.get("experience_min")
        if minimum is None or experience >= float(minimum):
            seniority_modifier = 5

    freshness_score = 5

    job_category = job.get("category") or categorize_job(
        job.get("title") or "", job.get("department") or "", job.get("description") or ""
    )
    course_category = categorize_course_name(course_name or "")
    category_match = "none"
    if job_category != OTHER_CATEGORY and course_category != OTHER_CATEGORY:
        if job_category == course_category:
            category_match = "exact"
        elif job_category in related_category_ids(course_category):
            category_match = "related"
    category_score = {"exact": 15, "related": 8, "none": 0}[category_match]

    base_score = (
        verified_score + skill_score + title_score + location_score
        + mode_score + freshness_score + category_score
    )
    score = max(5, min(100, base_score + seniority_modifier))

    reasons = []
    if seniority == "entry" and experience <= 1.0:
        reasons.append("🎓 Ideal for College Freshers / Entry-Level")
    elif seniority == "growth":
        reasons.append("🚀 Next-Step Career Growth Role")

    if category_match == "exact":
        label = category_labels().get(job_category, job_category)
        reasons.append(f"Matches your preferred role category: {label}")
    elif category_match == "related":
        label = category_labels().get(job_category, job_category)
        reasons.append(f"Related to your preferred role category: {label}")
    if verified_overlap:
        reasons.append("Skills from your preferred roles: " + ", ".join(sorted(verified_overlap)[:4]))
    if declared_overlap:
        reasons.append("Profile skills: " + ", ".join(sorted(declared_overlap)[:4]))
    if title_score:
        reasons.append("Matches your preferred role")
    if location_score == 10:
        reasons.append("Matches your preferred location")
    if mode_score == 5:
        reasons.append("Matches your work-mode preference")
    if not reasons:
        reasons.append("Active opportunity that matches your profile")

    return score, reasons


def blend_job_matches(
    scored_jobs: List[Dict[str, Any]],
    limit: int = 5,
    entry_ratio: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Blends jobs ensuring:
    - ~70% Entry / Fresher opportunities
    - ~30% Growth / Next-step opportunities
    - Excludes heavily penalized senior/AVP roles from top slots
    """
    if not scored_jobs:
        return []

    entry_jobs = [j for j in scored_jobs if j.get("seniority_tier") == "entry" and j.get("match_score", 0) > 10]
    growth_jobs = [j for j in scored_jobs if j.get("seniority_tier") == "growth" and j.get("match_score", 0) > 10]
    other_jobs = [j for j in scored_jobs if j not in entry_jobs and j not in growth_jobs]

    entry_target = math.ceil(limit * entry_ratio)  # e.g. 4 out of 5
    growth_target = limit - entry_target          # e.g. 1 out of 5

    selected_entry = entry_jobs[:entry_target]
    selected_growth = growth_jobs[:growth_target]

    # If entry jobs are fewer than target, backfill from growth, then other
    blended = list(selected_entry) + list(selected_growth)
    if len(blended) < limit:
        remaining_slots = limit - len(blended)
        for pool in (growth_jobs[len(selected_growth):], entry_jobs[len(selected_entry):], other_jobs):
            for candidate in pool:
                if candidate not in blended:
                    blended.append(candidate)
                    if len(blended) >= limit:
                        break
            if len(blended) >= limit:
                break

    # Final sort preserving entry-first priority
    blended.sort(key=lambda x: (x.get("seniority_tier") == "entry", x.get("match_score", 0)), reverse=True)
    return blended[:limit]
