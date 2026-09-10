import json
import re

from .categories import OTHER_CATEGORY, categorize_course_name, categorize_job, category_labels, related_category_ids


STOP_WORDS = {
    "and", "the", "for", "with", "from", "course", "final", "exam",
    "developer", "engineer", "specialist", "associate", "junior", "senior",
}


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


def score_job(job, profile, course_name):
    job_skills = _tokens(parse_list(job.get("skills")))
    student_skills = _tokens(parse_list(profile.get("skills")))
    course_skills = _tokens([course_name or ""])
    title_preferences = [item.lower() for item in parse_list(profile.get("preferred_titles"))]
    location_preferences = [item.lower() for item in parse_list(profile.get("preferred_locations"))]

    verified_overlap = job_skills & course_skills
    declared_overlap = job_skills & student_skills
    required_count = max(1, len(job_skills))

    verified_score = min(40, round(40 * len(verified_overlap) / required_count))
    skill_score = min(25, round(25 * len(declared_overlap) / required_count))

    title = (job.get("title") or "").lower()
    title_score = 10 if any(pref in title for pref in title_preferences) else 0

    location = (job.get("location") or "").lower()
    location_score = 0
    if not location_preferences:
        location_score = 5
    elif any(pref in location for pref in location_preferences):
        location_score = 10

    preferred_mode = (profile.get("preferred_work_mode") or "").lower()
    job_mode = (job.get("work_mode") or "").lower()
    mode_score = 10 if preferred_mode and preferred_mode == job_mode else (5 if not preferred_mode else 0)

    experience = float(profile.get("experience_years") or 0)
    minimum = job.get("experience_min")
    experience_score = 10 if minimum is None or experience >= float(minimum) else 0
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

    score = min(
        100,
        verified_score + skill_score + title_score + location_score
        + mode_score + experience_score + freshness_score + category_score,
    )
    reasons = []
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
    if mode_score == 10:
        reasons.append("Matches your work-mode preference")
    if not reasons:
        reasons.append("Active opportunity that matches your profile")

    return score, reasons
