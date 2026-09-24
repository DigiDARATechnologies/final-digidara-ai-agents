import math
import re
from collections import Counter
from datetime import date, datetime, timezone

from app.services.ats_config import (
    ACTION_VERBS,
    JOB_MATCH_WEIGHTS,
    QUALITY_WEIGHTS,
    SCORING_VERSION,
    SKILL_ALIASES,
    STOP_WORDS,
    get_role_skills,
)


def analyze_resume(parsed, original_text="", job_description="", extraction_warnings=None, target_role=""):
    parsed = parsed or {}
    original_text = original_text or ""
    job_description = (job_description or "").strip()
    target_role = (target_role or "").strip()
    if not resume_has_minimum_content(parsed, original_text):
        raise ValueError("Resume content is too empty to analyze.")
    scoring_requirements = "\n".join(filter(None, [
        f"Target role: {target_role}" if target_role else "",
        job_description,
    ]))
    if scoring_requirements:
        return score_job_match(parsed, original_text, scoring_requirements, extraction_warnings or [])
    return score_resume_quality(parsed, original_text, extraction_warnings or [])


def score_job_match(parsed, original_text, job_description, extraction_warnings):
    jd = parse_job_description(job_description)
    resume_index = build_resume_index(parsed, original_text)
    breakdown = {}

    skill_result = score_skills(resume_index, jd)
    breakdown["skills"] = skill_result["category"]
    context_result = score_context(resume_index, jd)
    breakdown["context_relevance"] = context_result
    experience_result = score_experience(resume_index, jd)
    breakdown["experience"] = experience_result
    education_result = score_education(parsed, resume_index, jd)
    breakdown["education_certifications"] = education_result
    breakdown["completeness"] = score_completeness(parsed, resume_index)
    breakdown["content_quality"] = score_content_quality(resume_index)
    breakdown["parseability"] = score_parseability(original_text, parsed, extraction_warnings)

    normalized = normalize_breakdown(breakdown)
    confidence, reasons = confidence_level(parsed, original_text, jd, extraction_warnings)
    result = {
        "analysis_type": "job_match",
        "score": {
            "earned_points": round(sum(item["earned"] for item in breakdown.values()), 2),
            "applicable_points": round(sum(item["maximum"] for item in breakdown.values() if item["applicable"]), 2),
            "normalized_score": normalized,
            "classification": classify_score(normalized),
            "confidence": confidence,
            "confidence_reasons": reasons,
        },
        "breakdown": breakdown,
        "skills": skill_result["skills"],
        "requirements": build_requirement_rows(skill_result, experience_result, education_result),
        "strengths": build_strengths(breakdown, skill_result),
        "formatting_warnings": breakdown["parseability"]["warnings"],
        "recommendations": build_recommendations(breakdown, skill_result, experience_result),
        "metadata": metadata(original_text, extraction_warnings, jd),
        "clarification": (
            "This score estimates how closely the resume matches the supplied job description using "
            "transparent content and formatting checks. It does not guarantee selection or represent every employer's ATS."
        ),
    }
    return with_legacy_aliases(result)


def score_resume_quality(parsed, original_text, extraction_warnings):
    resume_index = build_resume_index(parsed, original_text)
    breakdown = {
        "section_completeness": quality_category("Section completeness", section_completeness(parsed), 25, "Core resume sections are present."),
        "content_clarity": quality_category("Content clarity and relevance", clarity_score(resume_index), 20, "Summary and section text are specific and readable."),
        "bullet_quality": quality_category("Experience and project bullet quality", bullet_quality_score(resume_index), 20, "Bullets use action verbs, concrete work, and concise wording."),
        "skills_organization": quality_category("Skills organization", skills_org_score(parsed), 15, "Skills are specific, deduplicated, and grouped clearly."),
        "parseability": score_parseability(original_text, parsed, extraction_warnings, maximum=15),
        "contact_quality": quality_category("Contact information quality", contact_quality(parsed), 5, "Name, email, phone, and location are checked."),
    }
    normalized = normalize_breakdown(breakdown)
    confidence, reasons = confidence_level(parsed, original_text, {"requirements": []}, extraction_warnings)
    result = {
        "analysis_type": "resume_quality",
        "score": {
            "earned_points": round(sum(item["earned"] for item in breakdown.values()), 2),
            "applicable_points": 100,
            "normalized_score": normalized,
            "classification": classify_score(normalized),
            "confidence": confidence,
            "confidence_reasons": reasons,
        },
        "breakdown": breakdown,
        "skills": {"matched_required": [], "missing_required": [], "matched_preferred": [], "missing_preferred": [], "additional_relevant": []},
        "requirements": [],
        "strengths": build_strengths(breakdown, {"skills": {}}),
        "formatting_warnings": breakdown["parseability"]["warnings"],
        "recommendations": build_quality_recommendations(breakdown),
        "metadata": metadata(original_text, extraction_warnings, {"requirements": []}),
        "clarification": "This resume quality score checks completeness, content quality, and parseability without a job description.",
    }
    return with_legacy_aliases(result)


def normalize_skill(value):
    text = re.sub(r"[^a-zA-Z0-9+#.]+", " ", str(value or "")).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return SKILL_ALIASES.get(text)


def skill_pattern(alias):
    return re.compile(rf"(?<![A-Za-z0-9+#.]){re.escape(alias)}(?![A-Za-z0-9+#.])", re.I)


def find_skill_evidence(text, section):
    found = {}
    for alias, canonical in SKILL_ALIASES.items():
        match = skill_pattern(alias).search(text or "")
        if match:
            found.setdefault(canonical, []).append({"section": section, "text": match.group(0)})
    return found


def build_resume_index(parsed, original_text):
    sections = []
    info = parsed.get("personalInfo") or {}
    add_section(sections, "summary", parsed.get("summary"))
    for item in parsed.get("skills") or []:
        add_section(sections, "skills", item.get("skill_name") if isinstance(item, dict) else item)
    for item in parsed.get("experience") or []:
        start_date = item.get("start_date") or item.get("startDate")
        end_date = item.get("end_date") or item.get("endDate")
        date_range = f"{start_date} - {end_date or 'Present'}" if start_date else ""
        add_section(sections, "experience", " ".join(str(value) for value in [
            item.get("role"), item.get("company"), date_range, item.get("raw_input"),
            " ".join(item.get("ai_generated_bullets") or []),
        ] if value))
    for item in parsed.get("projects") or []:
        add_section(sections, "projects", " ".join(filter(None, [item.get("title"), item.get("description")])))
    for item in parsed.get("publications") or []:
        add_section(sections, "publications", " ".join(filter(None, [item.get("title"), item.get("description")])))
    for item in parsed.get("education") or []:
        add_section(sections, "education", " ".join(filter(None, [item.get("degree"), item.get("field"), item.get("school")])))
    for item in parsed.get("certifications") or []:
        add_section(sections, "certifications", " ".join(filter(None, [item.get("name"), item.get("issuer")])))
    evidence = {}
    for section in sections:
        for skill, items in find_skill_evidence(section["text"], section["section"]).items():
            evidence.setdefault(skill, []).extend(items)
    text = "\n".join([original_text, *(item["text"] for item in sections), *(str(v) for v in info.values() if v)])
    bullets = []
    for section in sections:
        bullets.extend([line.strip(" -*•") for line in section["text"].split("\n") if len(line.strip()) > 12])
    return {"sections": sections, "text": text, "skill_evidence": evidence, "bullets": bullets}


def add_section(sections, section, text):
    if text and str(text).strip():
        sections.append({"section": section, "text": str(text).strip()})


def parse_job_description(text):
    required, preferred = [], []
    responsibilities = []
    lower_lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lower_lines:
        line_lower = line.lower()
        skills = extract_skills_from_text(line)
        if re.search(r"\b(required|must have|mandatory|minimum)\b", line_lower):
            required.extend(skills)
        elif re.search(r"\b(preferred|nice to have|good to have|plus)\b", line_lower):
            preferred.extend(skills)
        elif re.match(r"^(?:target\s+)?(?:job\s+)?(?:title|role|position)\s*[:\-]", line, re.I):
            # A title identifies the role, but is not a responsibility to compare
            # against resume bullets.
            continue
        else:
            responsibilities.append(line)
    all_skills = extract_skills_from_text(text)
    if not required and not preferred:
        counts = Counter(all_skills)
        required = [skill for skill, _count in counts.most_common(max(1, min(8, len(counts))))]
    role_title = detect_job_title(text)
    if not required and not preferred and role_title:
        role_skills = get_role_skills(role_title)
        if role_skills:
            required = list(role_skills)
    required = dedupe(required)
    preferred = [skill for skill in dedupe(preferred) if skill not in required]
    known_skills = {skill.lower() for skill in required + preferred}
    free_text_required = [
        phrase for phrase in extract_free_text_requirements(text)
        if phrase.lower() not in known_skills
    ]
    word_count = len(tokenize(text))
    skills_applicable = bool(required or preferred or free_text_required)
    responsibility_terms = tokenize(" ".join(responsibilities))
    responsibility_signal = re.compile(
        r"\b(responsib\w*|develop\w*|build\w*|design\w*|manage\w*|lead\w*|"
        r"analy[sz]\w*|create\w*|deliver\w*|collaborat\w*|own\w*|drive\w*|"
        r"support\w*|implement\w*|optimi[sz]\w*)\b",
        re.I,
    )
    # A role title or a skills-only prompt cannot support a fair context score.
    # Short, imperative duties such as "Build dashboards" remain valid.
    context_applicable = bool(responsibilities) and (
        len(responsibility_terms) >= 8 or any(responsibility_signal.search(line) for line in responsibilities)
    )
    return {
        "title": detect_job_title(text),
        "required_skills": required,
        "preferred_skills": preferred,
        "responsibilities": responsibilities,
        "minimum_years": detect_min_years(text),
        "education_required": bool(re.search(r"\b(bachelor|master|degree|b\.?tech|bsc|msc|mba)\b", text, re.I)),
        "certifications": extract_certifications(text),
        "requirements": required + preferred + free_text_required,
        "free_text_required": free_text_required,
        "skills_applicable": skills_applicable,
        "context_applicable": context_applicable,
        "job_description_is_thin": word_count < 18 and not skills_applicable,
    }


def extract_skills_from_text(text):
    skills = []
    for alias, canonical in SKILL_ALIASES.items():
        if skill_pattern(alias).search(text or ""):
            skills.append(canonical)
    return dedupe(skills)


def extract_free_text_requirements(text):
    """Supplement the vocabulary with explicit, list-like JD requirements."""
    phrases = []
    for line in (text or "").splitlines():
        if not re.search(r"\b(required|must have|mandatory|minimum)\b", line, re.I):
            continue
        candidate_text = re.split(r"[:\-]", line, maxsplit=1)[-1]
        for phrase in re.split(r"[,;/]|\band\b", candidate_text, flags=re.I):
            phrase = re.sub(r"\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?).*", "", phrase, flags=re.I).strip(" .:-")
            words = tokenize(phrase)
            if 1 <= len(words) <= 4 and not any(word in {"experience", "skills", "skill", "required", "minimum"} for word in words):
                phrases.append(" ".join(words).title())
    return dedupe(phrases)


def phrase_evidence(phrase, sections):
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", re.I)
    return [
        {"section": section["section"], "text": phrase}
        for section in sections if pattern.search(section["text"])
    ]


def score_skills(resume_index, jd):
    evidence = resume_index["skill_evidence"]
    required = jd["required_skills"] + jd.get("free_text_required", [])
    preferred = jd["preferred_skills"]
    def evidence_for(skill):
        return evidence.get(skill) or phrase_evidence(skill, resume_index["sections"])
    matched_required = [{"skill": skill, "evidence": evidence_for(skill)} for skill in required if evidence_for(skill)]
    missing_required = [{"skill": skill, "evidence": []} for skill in required if not evidence_for(skill)]
    matched_preferred = [{"skill": skill, "evidence": evidence_for(skill)} for skill in preferred if evidence_for(skill)]
    missing_preferred = [{"skill": skill, "evidence": []} for skill in preferred if not evidence_for(skill)]
    req_max = 24 if required else 0
    pref_max = 6 if preferred else 0
    earned = (len(matched_required) / len(required) * req_max if required else 0) + (len(matched_preferred) / len(preferred) * pref_max if preferred else 0)
    applicable = jd.get("skills_applicable", bool(required or preferred))
    if not applicable:
        earned = 0
    explanation = (
        f"Matched {len(matched_required)} of {len(required)} required requirement(s) and "
        f"{len(matched_preferred)} of {len(preferred)} preferred requirement(s). "
        "Required requirements account for up to 24 points; preferred requirements account for up to 6 points. "
        "Evidence is checked in Skills, Summary, Experience, Projects, Publications, Education, and Certifications."
    )
    return {
        "category": make_breakdown("Skills Match", earned, JOB_MATCH_WEIGHTS["skills"], applicable, explanation, matched_required[:4], "Add only genuinely known missing skills with evidence in Skills, Experience, or Publications.", not_applicable_explanation="No explicit skills or requirements were found. Add a fuller job description (not just a title) for an accurate skills match."),
        "skills": {
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_preferred": matched_preferred,
            "missing_preferred": missing_preferred,
            "additional_relevant": [{"skill": skill, "evidence": items} for skill, items in evidence.items() if skill not in required and skill not in preferred],
        },
    }


def score_context(resume_index, jd):
    job_terms = tokenize(" ".join(jd["responsibilities"]))
    resume_terms = tokenize(" ".join(s["text"] for s in resume_index["sections"] if s["section"] in {"summary", "experience", "publications"}))
    similarity = cosine(job_terms, resume_terms)
    earned = similarity * JOB_MATCH_WEIGHTS["context_relevance"]
    applicable = jd.get("context_applicable", bool(job_terms))
    return make_breakdown(
        "Responsibilities and Context", earned, 20, applicable,
        f"Found {round(similarity * 100)}% contextual overlap between the job's stated duties and the resume's Summary, Experience, and Publications. "
        "This 20-point check compares meaningful terms in responsibility statements; role titles and skills-only lines are excluded.", [],
        "Mirror relevant responsibilities truthfully in bullets and summary.",
        not_applicable_explanation="Add actual responsibilities or day-to-day duties to the job description for a meaningful context comparison.",
    )


def score_experience(resume_index, jd):
    years_required = jd["minimum_years"]
    experience_text = "\n".join(
        section["text"] for section in resume_index["sections"]
        if section["section"] == "experience"
    )
    years_found = estimate_years(experience_text)
    title = jd["title"]
    title_score = lexical_overlap(title, resume_index["text"]) if title else 1
    if years_required is None:
        earned = title_score * 15
        applicable = bool(title)
        explanation = (
            f"No minimum years were specified, so duration is not scored. This category uses target-title alignment only: {round(title_score * 100)}% of target-title terms appear in the resume."
            if title else "Add a target role or minimum-years requirement to evaluate experience alignment."
        )
    else:
        years_score = min(1, years_found / years_required) if years_required else 1
        earned = (years_score * 0.7 + title_score * 0.3) * 15
        applicable = True
        explanation = (
            f"Detected about {years_found:.1f} years of dated experience against {years_required:.1f} required years. "
            f"Duration contributes 70% and target-title alignment ({round(title_score * 100)}%) contributes 30% of this 15-point category."
        )
    return make_breakdown("Experience and Title Alignment", earned, 15, applicable, explanation, [], "Clarify relevant dates, job titles, and domain experience.", not_applicable_explanation="Add a target role or minimum-years requirement to evaluate experience alignment.")


def score_education(parsed, resume_index, jd):
    applicable = jd["education_required"] or bool(jd["certifications"])
    text = resume_index["text"]
    earned = 0
    if jd["education_required"] and re.search(r"\b(bachelor|master|degree|b\.?tech|bsc|msc|mba)\b", text, re.I):
        earned += 7
    elif jd["education_required"]:
        earned += 2
    if jd["certifications"]:
        matched = [cert for cert in jd["certifications"] if re.search(rf"(?<!\w){re.escape(cert)}(?!\w)", text, re.I)]
        earned += 3 * (len(matched) / len(jd["certifications"]))
    elif jd["education_required"]:
        earned += 3
    education_detail = "A degree requirement was found." if jd["education_required"] else "No degree requirement was found."
    certification_detail = (
        f" Matched {len(matched)} of {len(jd['certifications'])} requested certification(s)."
        if jd["certifications"] else " No certification requirement was found."
    )
    return make_breakdown(
        "Education and Certifications", earned, 10, applicable,
        f"Only explicitly stated requirements are scored: up to 7 points for education and up to 3 points for certifications. {education_detail}{certification_detail}",
        [], "Add required education or certifications only when true.",
        not_applicable_explanation="The job description does not state an education or certification requirement, so this category is excluded from the estimate.",
    )


def score_completeness(parsed, resume_index):
    info = parsed.get("personalInfo") or {}
    checks = {
        "contact information": bool(info.get("fullName") and info.get("email")),
        "professional summary": bool(str(parsed.get("summary") or "").strip()),
        "skills": bool(parsed.get("skills")),
        "experience": bool(parsed.get("experience")),
        "education": bool(parsed.get("education")),
    }
    missing = [label for label, present in checks.items() if not present]
    earned = sum(checks.values()) / len(checks) * 10
    present_count = len(checks) - len(missing)
    explanation = (
        f"{present_count} of {len(checks)} core checks are complete: contact information (name and email), professional summary, skills, experience, and education. "
        + ("All core sections are present." if not missing else f"Missing or incomplete: {', '.join(missing)}.")
    )
    action = "No core sections are missing." if not missing else f"Add meaningful content for: {', '.join(missing)}."
    return make_breakdown("Completeness and Section Quality", earned, 10, True, explanation, [], action)


def score_content_quality(resume_index):
    bullets = resume_index["bullets"]
    if not bullets:
        earned = 1
        explanation = "No substantial experience or project bullets were detected. This 5-point check rewards action-led, concise bullets with measurable outcomes."
    else:
        action = sum(first_word(bullet) in ACTION_VERBS for bullet in bullets)
        metrics = sum(bool(re.search(r"\b\d+(?:\.\d+)?%|\b\d+\s*(hours|users|reports|projects|clients|records)\b", bullet, re.I)) for bullet in bullets)
        concise = sum(8 <= len(bullet.split()) <= 32 for bullet in bullets)
        earned = ((action + concise) / (len(bullets) * 2) * 4) + min(1, metrics / max(1, len(bullets) * 0.5))
        explanation = (
            f"Reviewed {len(bullets)} substantial bullet(s): {action} begin with a recognized action verb, "
            f"{concise} are 8–32 words, and {metrics} contain a measurable outcome. "
            "These signals make accomplishments easier for recruiters and ATS reviewers to interpret."
        )
    return make_breakdown("Achievement and Content Quality", earned, 5, True, explanation, [], "Use action-led bullets with truthful scope and outcomes.")


def score_parseability(original_text, parsed, extraction_warnings, maximum=10):
    words = len(tokenize(original_text))
    warnings = []
    earned = maximum
    if words < 80:
        earned -= maximum * 0.45
        warnings.append({"severity": "critical", "problem": "Low extracted text volume", "fix": "Upload a text-based PDF or DOCX file."})
    if extraction_warnings:
        earned -= maximum * 0.25
        warnings.extend({"severity": "warning", "problem": warning, "fix": "Review extracted text before trusting the score."} for warning in extraction_warnings)
    if re.search(r"[■◆●★]{2,}", original_text):
        earned -= maximum * 0.15
        warnings.append({"severity": "warning", "problem": "Decorative symbols detected", "fix": "Use plain bullets and headings."})
    explanation = (
        f"Reviewed {words} extracted word(s) for ATS-readable text, decorative-symbol risk, and extraction warnings. "
        f"{len(warnings)} issue(s) affected this {maximum}-point formatting check. "
        "This measures whether the uploaded file can be reliably read; it does not judge visual design."
    )
    return make_breakdown("ATS Parseability and Formatting", earned, maximum, True, explanation, [], "Use simple text-based layouts and clear section headings.") | {"warnings": warnings}


def make_breakdown(label, earned, maximum, applicable, explanation, evidence, action, not_applicable_explanation=None):
    earned = max(0, min(maximum, float(earned)))
    status = "Not Applicable" if not applicable else "Passed" if earned >= maximum * .8 else "Warning" if earned >= maximum * .45 else "Critical"
    if not applicable:
        explanation = not_applicable_explanation or "Not enough job description detail to check this."
        action = None
    return {"label": label, "earned": round(earned, 2), "maximum": maximum, "applicable": applicable, "status": status, "explanation": explanation, "evidence": evidence or [], "improvement_action": action}


def normalize_breakdown(breakdown):
    applicable = [item for item in breakdown.values() if item["applicable"]]
    earned = sum(item["earned"] for item in applicable)
    maximum = sum(item["maximum"] for item in applicable)
    return int(round((earned / maximum) * 100)) if maximum else 0


def with_legacy_aliases(result):
    score = result["score"]["normalized_score"]
    result["legacyScore"] = score
    result["normalizedScore"] = score
    result["rating"] = result["score"]["classification"]
    result["summary"] = result["clarification"]
    result["categories"] = [
        {"category": item["label"], "pointsEarned": item["earned"], "maxPoints": item["maximum"], "status": item["status"], "applicable": item["applicable"], "explanation": item["explanation"], "recommendedAction": item["improvement_action"]}
        for item in result["breakdown"].values()
    ]
    result["passedChecks"] = len([item for item in result["categories"] if item["status"] == "Passed"])
    result["warningCount"] = len([item for item in result["categories"] if item["status"] == "Warning"])
    result["criticalIssueCount"] = len([item for item in result["categories"] if item["status"] == "Critical"])
    result["criticalIssues"] = [{"section": rec["section"], "problem": rec["problem"], "whyItMatters": rec["why_it_matters"]} for rec in result["recommendations"] if rec["priority"] == "Critical"]
    result["jobMatch"] = None
    if result["analysis_type"] == "job_match":
        missing = [item["skill"] for item in result["skills"]["missing_required"] + result["skills"]["missing_preferred"]]
        matched = [item["skill"] for item in result["skills"]["matched_required"] + result["skills"]["matched_preferred"]]
        result["jobMatch"] = {"score": score, "matchedKeywords": matched, "missingKeywords": missing, "keywordsEvaluated": len(matched) + len(missing), "method": "Deterministic weighted evidence-based scoring."}
    return result


def classify_score(score):
    if score >= 85:
        return "Excellent Match"
    if score >= 70:
        return "Strong Match"
    if score >= 55:
        return "Moderate Match"
    if score >= 40:
        return "Weak Match"
    return "Low Match"


def quality_category(label, earned, maximum, explanation):
    return make_breakdown(label, earned, maximum, True, explanation, [], "Improve this section with truthful, specific content.")


def section_completeness(parsed):
    checks = ["summary", "skills", "experience", "education", "publications"]
    return sum(bool(parsed.get(key)) for key in checks) / len(checks) * 25


def clarity_score(index):
    text = index["text"]
    words = len(tokenize(text))
    repeated = max(0, len(index["bullets"]) - len(set(b.lower() for b in index["bullets"])))
    return max(0, min(20, (min(words, 600) / 600 * 14) + 6 - repeated))


def bullet_quality_score(index):
    return score_content_quality(index)["earned"] / 5 * 20


def skills_org_score(parsed):
    skills = []
    for item in parsed.get("skills") or []:
        value = item.get("skill_name") if isinstance(item, dict) else item
        skills.extend([part.strip() for part in re.split(r"[,;:]", str(value or "")) if part.strip()])
    unique = len({s.lower() for s in skills})
    return min(15, unique * 1.5) - (2 if unique != len(skills) else 0)


def contact_quality(parsed):
    info = parsed.get("personalInfo") or {}
    return sum([bool(info.get("fullName")), bool(re.search(r"@", info.get("email") or "")), bool(info.get("phone")), bool(info.get("location")), bool(info.get("linkedin") or info.get("github") or info.get("portfolio"))])


def tokenize(text):
    return [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}", text or "") if word.lower() not in STOP_WORDS]


def cosine(a, b):
    ca, cb = Counter(a), Counter(b)
    if not ca or not cb:
        return 0
    dot = sum(ca[key] * cb.get(key, 0) for key in ca)
    return min(1, dot / (math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))))


def lexical_overlap(needle, haystack):
    terms = set(tokenize(needle))
    if not terms:
        return 0
    hay = set(tokenize(haystack))
    return len(terms & hay) / len(terms)


def detect_min_years(text):
    match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)", text or "", re.I)
    return float(match.group(1)) if match else None


def detect_job_title(text):
    match = re.search(r"(?:target\s+)?(?:job\s+)?(?:title|role|position)\s*[:\-]\s*([A-Za-z /+_\-]{3,80})", text or "", re.I)
    return match.group(1).strip() if match else ""


def extract_certifications(text):
    return dedupe(re.findall(r"\b(?:AWS|Azure|PMP|CPA|CFA|CompTIA|Cisco|Google Cloud)[A-Za-z0-9 +#.-]*", text or "", re.I))


MONTH_PATTERN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_TOKEN_PATTERN = rf"(?:{MONTH_PATTERN}\.?(?:\s*,)?\s+(?:19|20)\d{{2}}|(?:19|20)\d{{2}}(?:[-/]\d{{1,2}}(?:[-/]\d{{1,2}})?)?)"


def parse_experience_date(value, is_end=False, today=None):
    value = str(value or "").strip()
    today = today or date.today()
    if re.fullmatch(r"(?:present|current|ongoing|now)", value, re.I):
        return date(today.year, today.month, 1)
    iso_match = re.fullmatch(r"(?P<year>(?:19|20)\d{2})[-/](?P<month>\d{1,2})(?:[-/]\d{1,2})?", value)
    if iso_match:
        return date(int(iso_match.group("year")), int(iso_match.group("month")), 1)
    month_match = re.fullmatch(rf"(?P<month>{MONTH_PATTERN})\.?(?:\s*,)?\s+(?P<year>(?:19|20)\d{{2}})", value, re.I)
    if month_match:
        month = datetime.strptime(month_match.group("month")[:3].title(), "%b").month
        return date(int(month_match.group("year")), month, 1)
    year_match = re.fullmatch(r"(?:19|20)\d{2}", value)
    if year_match:
        return date(int(value), 12 if is_end else 1, 1)
    return None


def experience_date_ranges(text, today=None):
    today = today or date.today()
    ranges = []
    pattern = re.compile(
        rf"(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|\u2013|\u2014|to)\s*(?P<end>{DATE_TOKEN_PATTERN}|present|current|ongoing|now)",
        re.I,
    )
    for match in pattern.finditer(text or ""):
        start = parse_experience_date(match.group("start"), today=today)
        end = parse_experience_date(match.group("end"), is_end=True, today=today)
        if start and end:
            ranges.append((start, max(start, min(end, date(today.year, today.month, 1)))))
    return ranges


def estimate_years(text, today=None):
    """Estimate only dated work intervals supplied by the Experience section."""
    ranges = sorted(experience_date_ranges(text, today=today))
    if ranges:
        merged = []
        for start, end in ranges:
            if merged and start <= date(merged[-1][1].year + (merged[-1][1].month == 12), (merged[-1][1].month % 12) + 1, 1):
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        months = sum((end.year - start.year) * 12 + end.month - start.month + 1 for start, end in merged)
        return months / 12
    return 0


def build_requirement_rows(skill_result, experience_result, education_result):
    rows = []
    for group, status in (("matched_required", "Matched"), ("missing_required", "Missing"), ("matched_preferred", "Matched"), ("missing_preferred", "Missing")):
        for item in skill_result["skills"][group]:
            rows.append({"requirement": item["skill"], "status": status, "resume_evidence": item.get("evidence") or [], "recommendation": "Keep" if status == "Matched" else "Add only if genuinely known"})
    rows.append({"requirement": "Experience alignment", "status": "Matched" if experience_result["earned"] >= experience_result["maximum"] * .75 else "Partial", "resume_evidence": [], "recommendation": experience_result["improvement_action"]})
    if education_result["applicable"]:
        rows.append({"requirement": "Education/certification", "status": "Matched" if education_result["earned"] >= education_result["maximum"] * .75 else "Partial", "resume_evidence": [], "recommendation": education_result["improvement_action"]})
    return rows


def build_strengths(breakdown, skill_result):
    strengths = [item["label"] for item in breakdown.values() if item["earned"] >= item["maximum"] * .8]
    if skill_result.get("skills", {}).get("matched_required"):
        strengths.append("Evidence-backed required skills detected")
    return strengths[:8]


def build_recommendations(breakdown, skill_result, experience_result):
    recs = []
    for item in skill_result["skills"]["missing_required"][:3]:
        recs.append(recommendation("Critical", "Skills", f"Missing required skill: {item['skill']}", "Required skills strongly affect job-match scoring.", f"Add {item['skill']} only in Skills/Experience/Publications if you genuinely have it.", f"{item['skill']}: used in a verified publication or role."))
    for key, item in breakdown.items():
        if item["applicable"] and item["earned"] < item["maximum"] * .55:
            recs.append(recommendation("Important", item["label"], f"Low {item['label']} score", item["explanation"], item["improvement_action"], "Rewrite one bullet with action, tool, and truthful outcome."))
    return recs[:8]


def build_quality_recommendations(breakdown):
    return [recommendation("Important", item["label"], f"Improve {item['label']}", item["explanation"], item["improvement_action"], "Add a concise, evidence-backed bullet.") for item in breakdown.values() if item["earned"] < item["maximum"] * .65][:8]


def recommendation(priority, section, problem, why, fix, example):
    return {"priority": priority, "section": section, "problem": problem, "why_it_matters": why, "exact_fix": fix, "truthful_example": example}


def confidence_level(parsed, original_text, jd, warnings):
    reasons = []
    score = 0
    if len(tokenize(original_text)) >= 120:
        score += 1
    else:
        reasons.append("Resume extraction produced limited text.")
    if parsed.get("experience") or parsed.get("skills"):
        score += 1
    else:
        reasons.append("Few standard resume sections were detected.")
    if jd.get("requirements") or not jd:
        score += 1
    else:
        reasons.append("Few job requirements were identified.")
    if warnings:
        reasons.append("Extraction warnings were reported.")
    if score >= 3 and not warnings:
        return "High", []
    if score >= 2:
        return "Medium", reasons
    return "Low", reasons


def metadata(original_text, warnings, jd):
    quality = min(1, len(tokenize(original_text)) / 160)
    if warnings:
        quality = min(quality, 0.7)
    return {
        "scoring_version": SCORING_VERSION,
        "analyzed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "resume_extraction_quality": round(quality, 2),
        "identified_requirements": len(jd.get("requirements", [])),
    }


def resume_has_minimum_content(parsed, original_text):
    return len(tokenize(original_text)) >= 10 or any(parsed.get(key) for key in ("summary", "skills", "experience", "publications"))


def first_word(text):
    words = tokenize(text)
    return words[0] if words else ""


def dedupe(values):
    result = []
    seen = set()
    for value in values:
        key = str(value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(str(value).strip() if not isinstance(value, str) else value)
    return result
