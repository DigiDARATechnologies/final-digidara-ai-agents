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


from .experience import (
    classify_job_seniority,
    extract_experience_from_text,
    format_experience_badge,
    is_fresher_eligible,
)


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
            seniority_modifier = 15   # Strong boost for genuine fresher/intern/entry roles
        elif seniority == "growth":
            seniority_modifier = 0    # Neutral baseline for growth roles
        elif seniority == "senior":
            seniority_modifier = -40  # Heavy penalty for senior / 4+ yr roles
    else:
        # User has experience
        minimum = job.get("experience_min")
        if minimum is not None:
            try:
                min_val = float(minimum)
                if experience >= min_val:
                    seniority_modifier = 10
                elif experience < min_val:
                    seniority_modifier = -30
            except (ValueError, TypeError):
                pass
        else:
            if seniority == "growth":
                seniority_modifier = 10
            elif seniority == "senior" and experience >= 4.0:
                seniority_modifier = 10

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

    has_candidate_intent = bool(student_skills or title_preferences)
    has_relevance = bool(declared_overlap or verified_overlap or title_score or category_match != "none")

    # If the candidate has declared technical skills or preferred titles,
    # but the job matches NONE of them (0 skills, 0 title match, unrelated category),
    # it is not relevant to their career goals and should not be scored as a match.
    if has_candidate_intent and not has_relevance:
        return 0, ["Unrelated to your technical skills or role preferences"]

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
    is_fresher_candidate: bool = False,
) -> List[Dict[str, Any]]:
    """
    Blends jobs ensuring:
    - If is_fresher_candidate is True: 100% genuine entry/fresher jobs.
      Zero senior or 4+ year jobs are ever leaked to freshers!
    - Otherwise: allocates career-aligned growth / mid-level roles matching candidate experience.
    - Highest matching score is ALWAYS presented first.
    """
    if not scored_jobs:
        return []

    entry_jobs = [j for j in scored_jobs if j.get("seniority_tier") == "entry" and j.get("match_score", 0) > 10]
    growth_jobs = [j for j in scored_jobs if j.get("seniority_tier") == "growth" and j.get("match_score", 0) > 10]
    senior_jobs = [j for j in scored_jobs if j.get("seniority_tier") == "senior" and j.get("match_score", 0) > 10]
    other_jobs = [j for j in scored_jobs if j not in entry_jobs and j not in growth_jobs and j not in senior_jobs and j.get("match_score", 0) > 10]

    if is_fresher_candidate:
        # Strictly select entry/fresher jobs first
        selected = list(entry_jobs[:limit])
        if len(selected) < limit:
            # Backfill strictly from growth roles that have NO senior requirements
            for cand in growth_jobs:
                if cand not in selected and is_fresher_eligible(cand):
                    selected.append(cand)
                    if len(selected) >= limit:
                        break
        selected.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return selected[:limit]

    # For experienced candidates: prioritize growth / career-matching roles first
    growth_target = math.ceil(limit * (1.0 - min(entry_ratio, 0.3)))  # e.g. at least 70% growth/experienced
    entry_target = limit - growth_target

    selected_growth = growth_jobs[:growth_target]
    selected_entry = entry_jobs[:entry_target]

    blended = list(selected_growth) + list(selected_entry)
    if len(blended) < limit:
        for pool in (growth_jobs[len(selected_growth):], entry_jobs[len(selected_entry):], senior_jobs, other_jobs):
            for candidate in pool:
                if candidate not in blended:
                    blended.append(candidate)
                    if len(blended) >= limit:
                        break
            if len(blended) >= limit:
                break

    # Final sort preserving match quality (highest match score first!)
    blended.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return blended[:limit]
