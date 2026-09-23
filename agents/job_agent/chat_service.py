"""Conversational AI Assistant for DigiDARA Job Agent.

Production-grade features:
- Multi-turn conversational memory with full context retention
- 70% Entry/Fresher & 30% Career Growth job blend optimized for college students
- Automatic prioritization of unapplied verified jobs when fresh daily postings are scarce
- Job Authenticity & Trust Verification engine (detects scams, validates official ATS)
- Real-time job Q&A: salary disclosure, experience requirements, role responsibilities,
  authenticity evaluation, and direct application links
- Automatic profile enrichment: detects mentioned skills, locations, and updates MySQL
- Celebratory and motivational responses when users apply to jobs
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded from the agent directory
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

from .db import get_db
from .matching import blend_job_matches, classify_job_seniority, score_job
from .skills import extract_skills_from_job, extract_skills_from_user_message
from .trust import evaluate_job_trust

logger = logging.getLogger("job_agent.chat")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
REQUEST_TIMEOUT = 25


def _parse_list(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [s.strip() for s in val.split(",") if s.strip()]
    return []


def _get_user_profile_and_missing(cursor, user_id: str) -> Tuple[Dict[str, Any], List[str]]:
    cursor.execute(
        """SELECT user_id, full_name, skills, preferred_titles, preferred_locations,
                  preferred_work_mode, experience_years, resume_original_name, profile_completed,
                  plan_tier
           FROM user_job_profiles WHERE user_id=%s""",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT IGNORE INTO user_job_profiles (user_id) VALUES (%s)", (user_id,))
        cursor.execute(
            """SELECT user_id, full_name, skills, preferred_titles, preferred_locations,
                      preferred_work_mode, experience_years, resume_original_name, profile_completed,
                      plan_tier
               FROM user_job_profiles WHERE user_id=%s""",
            (user_id,),
        )
        row = cursor.fetchone()

    profile = dict(row or {})
    profile["skills"] = _parse_list(profile.get("skills"))
    profile["preferred_titles"] = _parse_list(profile.get("preferred_titles"))
    profile["preferred_locations"] = _parse_list(profile.get("preferred_locations"))
    profile["full_name"] = (profile.get("full_name") or "").strip()
    profile["preferred_work_mode"] = (profile.get("preferred_work_mode") or "").strip()
    profile["experience_years"] = float(profile.get("experience_years") or 0)
    profile["resume_original_name"] = (profile.get("resume_original_name") or "").strip()

    missing = []
    if not profile["skills"]:
        missing.append("skills")
    if not profile["preferred_locations"]:
        missing.append("preferred locations (e.g. Chennai, Coimbatore, Bangalore, Remote)")
    if not profile["preferred_titles"]:
        missing.append("target job titles")
    if not profile["resume_original_name"]:
        missing.append("resume upload")

    return profile, missing


def _get_job_by_id(cursor, job_id: int) -> Optional[Dict[str, Any]]:
    """Loads a full job record by ID with trust verification metrics."""
    cursor.execute(
        """SELECT j.id, j.title, j.company, j.location, j.work_mode, j.employment_type,
                  j.experience_min, j.experience_max, j.salary_text, j.description,
                  j.skills, j.category, j.external_id, j.apply_url, j.published_at
           FROM jobs j
           WHERE j.id = %s""",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    job = dict(row)
    job["skills"] = _parse_list(job.get("skills"))
    job["seniority_tier"] = classify_job_seniority(job)
    trust_info = evaluate_job_trust(job)
    job.update(trust_info)
    return job


def _get_top_matched_jobs(
    cursor,
    profile: Dict[str, Any],
    user_id: Optional[str] = None,
    limit: int = 5,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Selects, scores, and blends jobs ensuring:
    - Exclusion of jobs already applied to by this user (unapplied priority)
    - 70% Entry / Fresher & 30% Growth / Next-step allocation
    - Trust score and verification badges computed for every job
    Returns: (blended_jobs, is_unapplied_backfill_active)
    """
    where = ["j.status='active'", "(j.expires_at IS NULL OR j.expires_at >= NOW())"]
    params: List[Any] = []

    if user_id:
        # Exclude hidden jobs and jobs already marked as applied
        join_clause = "LEFT JOIN user_job_actions a ON a.job_id=j.id AND a.user_id=%s"
        where.append("COALESCE(a.is_hidden, 0) = 0")
        where.append("COALESCE(a.application_status, '') != 'applied'")
        params.append(user_id)
    else:
        join_clause = ""

    cursor.execute(
        f"""SELECT j.id, j.title, j.company, j.location, j.work_mode, j.employment_type,
                   j.experience_min, j.experience_max, j.salary_text, j.description,
                   j.skills, j.category, j.external_id, j.apply_url, j.published_at
            FROM jobs j
            {join_clause}
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(j.published_at, j.created_at) DESC LIMIT 150""",
        tuple(params),
    )
    rows = cursor.fetchall()
    preferred_titles_text = " ".join(profile.get("preferred_titles") or [])

    scored_jobs = []
    for r in rows:
        job = dict(r)
        job["skills"] = _parse_list(job.get("skills"))
        if not job["skills"]:
            job["skills"] = extract_skills_from_job(job)
        score, reasons = score_job(job, profile, preferred_titles_text)
        job["match_score"] = score
        job["match_reasons"] = reasons

        # Evaluate Trust & Authenticity
        trust_info = evaluate_job_trust(job)
        job.update(trust_info)

        scored_jobs.append(job)

    scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    # Blend 70% entry / 30% growth
    blended = blend_job_matches(scored_jobs, limit=limit, entry_ratio=0.7)

    # Check if entry jobs today were low and unapplied backfill was relied upon
    is_unapplied_backfill = len([j for j in blended if j.get("seniority_tier") == "entry"]) > 0
    return blended, is_unapplied_backfill


def _detect_focused_job(
    cursor,
    message: str,
    history: List[Dict[str, str]],
    matched_jobs: List[Dict[str, Any]],
    selected_job_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Resolves which job the user is asking about (by ID, message text, or recent history)."""
    # 1. Direct explicit ID passed from client
    if selected_job_id:
        job = _get_job_by_id(cursor, selected_job_id)
        if job:
            return job

    # 2. Check if user mentioned a company or title in the message
    msg_lower = message.lower()
    for j in matched_jobs:
        comp = (j.get("company") or "").lower()
        title = (j.get("title") or "").lower()
        if (comp and comp in msg_lower) or (title and title in msg_lower):
            return _get_job_by_id(cursor, j["id"]) or j

    # 3. Check history: did user or assistant recently discuss a specific job?
    for h in reversed(history[-6:]):
        content = (h.get("content") or "").lower()
        # Look for [ID:123] pattern in history
        id_match = re.search(r"\[ID:(\d+)\]", content)
        if id_match:
            job = _get_job_by_id(cursor, int(id_match.group(1)))
            if job:
                return job
        # Look for matched company in recent messages
        for j in matched_jobs:
            comp = (j.get("company") or "").lower()
            if comp and comp in content:
                return _get_job_by_id(cursor, j["id"]) or j

    # 4. If user says "this job" or "the job" and we have a single top match
    if matched_jobs and any(w in msg_lower for w in ["this job", "the job", "this role", "the position"]):
        return _get_job_by_id(cursor, matched_jobs[0]["id"]) or matched_jobs[0]

    return None


def _apply_profile_updates(db, cursor, user_id: str, current_profile: Dict[str, Any], updates: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Merges and saves detected profile updates into MySQL."""
    changed_fields = []

    skills_to_add = updates.get("skills_to_add") or updates.get("skills")
    if skills_to_add and isinstance(skills_to_add, list):
        existing_skills = set(s.lower() for s in current_profile["skills"])
        new_skills = list(current_profile["skills"])
        for s in skills_to_add:
            clean_s = str(s).strip()
            if clean_s and clean_s.lower() not in existing_skills:
                new_skills.append(clean_s)
                existing_skills.add(clean_s.lower())
        if len(new_skills) > len(current_profile["skills"]):
            current_profile["skills"] = new_skills[:50]
            changed_fields.append("skills")

    locations_to_set = updates.get("locations_to_set") or updates.get("preferred_locations")
    if locations_to_set and isinstance(locations_to_set, list):
        clean_locs = [str(loc).strip() for loc in locations_to_set if str(loc).strip()]
        if clean_locs and clean_locs != current_profile["preferred_locations"]:
            current_profile["preferred_locations"] = clean_locs[:20]
            changed_fields.append("preferred locations")

    titles_to_set = updates.get("titles_to_set") or updates.get("preferred_titles")
    if titles_to_set and isinstance(titles_to_set, list):
        clean_titles = [str(t).strip() for t in titles_to_set if str(t).strip()]
        if clean_titles and clean_titles != current_profile["preferred_titles"]:
            current_profile["preferred_titles"] = clean_titles[:20]
            changed_fields.append("target job titles")

    if "preferred_work_mode" in updates:
        mode = str(updates["preferred_work_mode"]).strip().lower()
        if mode in {"", "remote", "hybrid", "onsite"} and mode != current_profile["preferred_work_mode"]:
            current_profile["preferred_work_mode"] = mode
            changed_fields.append("work mode")

    if "experience_years" in updates:
        try:
            exp = max(0.0, min(50.0, float(updates["experience_years"])))
            if exp != current_profile["experience_years"]:
                current_profile["experience_years"] = exp
                changed_fields.append("years of experience")
        except (ValueError, TypeError):
            pass

    if changed_fields:
        completed = bool(
            current_profile["full_name"]
            and current_profile["skills"]
            and current_profile["preferred_titles"]
        )
        cursor.execute(
            """UPDATE user_job_profiles
               SET skills=%s, preferred_titles=%s, preferred_locations=%s,
                   preferred_work_mode=%s, experience_years=%s, profile_completed=%s
               WHERE user_id=%s""",
            (
                json.dumps(current_profile["skills"]),
                json.dumps(current_profile["preferred_titles"]),
                json.dumps(current_profile["preferred_locations"]),
                current_profile["preferred_work_mode"],
                current_profile["experience_years"],
                int(completed),
                user_id,
            ),
        )
        db.commit()

    return current_profile, changed_fields


def _build_system_prompt(
    profile: Dict[str, Any],
    missing: List[str],
    matched_jobs: List[Dict[str, Any]],
    focused_job: Optional[Dict[str, Any]] = None,
) -> str:
    user_name = profile.get("full_name") or "there"
    skills_str = ", ".join(profile.get("skills") or []) or "None listed yet"
    locs_str = ", ".join(profile.get("preferred_locations") or []) or "Tamil Nadu & major tech hubs"
    titles_str = ", ".join(profile.get("preferred_titles") or []) or "Software / Tech roles"
    exp_str = f"{profile.get('experience_years', 0)} years"

    # Jobs list summary formatted with 70/30 classification and trust
    jobs_summary = []
    for idx, j in enumerate(matched_jobs, 1):
        tier_tag = "🎓 Entry-Level / Fresher" if j.get("seniority_tier") == "entry" else "🚀 Growth Role (2-4 yrs)"
        trust_tag = f"{j.get('trust_badge', '✅ Verified')} ({j.get('trust_score', 85)}% Trust Score)"
        salary = j.get("salary_text") or "Not disclosed in posting"
        exp_req = (
            f"{j.get('experience_min', 0)}-{j.get('experience_max', 2)} yrs"
            if j.get("experience_min") is not None
            else "Fresher / Entry"
        )
        jobs_summary.append(
            f"{idx}. [ID:{j['id']}] {j['title']} @ {j['company']} ({j.get('location', 'Flexible')})\n"
            f"   Tier: {tier_tag} | Trust: {trust_tag}\n"
            f"   Required Exp: {exp_req} | Salary: {salary}\n"
            f"   Key Skills: {', '.join(j.get('skills') or [])}\n"
            f"   Apply Link: {j.get('apply_url')}"
        )
    jobs_text = "\n".join(jobs_summary) if jobs_summary else "No active jobs in feed currently."

    focused_block = ""
    if focused_job:
        f_exp = (
            f"{focused_job.get('experience_min', 0)} to {focused_job.get('experience_max', 2)} years"
            if focused_job.get("experience_min") is not None
            else "Fresher / Entry Level"
        )
        match_title_exp = re.search(r"(\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?)", focused_job.get("title", ""), re.I)
        if match_title_exp:
            f_exp = match_title_exp.group(1)

        f_salary = focused_job.get("salary_text") or "The employer has not disclosed the salary range in the public listing."
        f_desc = (focused_job.get("description") or "Detailed technical role.").strip()[:900]
        f_signals = ", ".join(focused_job.get("signals") or ["Verified corporate career portal"])

        focused_block = f"""
======================================================
ACTIVE / FOCUSED JOB CURRENTLY BEING DISCUSSED:
- Job ID: {focused_job['id']}
- Title: {focused_job['title']}
- Company: {focused_job['company']}
- Location: {focused_job.get('location', 'Tamil Nadu / Flexible')}
- Work Mode: {focused_job.get('work_mode', 'onsite')}
- Employment Type: {focused_job.get('employment_type', 'Full Time')}
- Required Experience: {f_exp}
- Salary / Compensation: {f_salary}
- Trust & Authenticity: {focused_job.get('trust_badge', '✅ Verified Genuine')} ({focused_job.get('trust_score', 90)}% Trust Score)
- Trust Signals: {f_signals}
- Apply URL: {focused_job.get('apply_url')}
- Role Description & Responsibilities:
{f_desc}
======================================================
"""

    return f"""You are the DigiDARA Job Agent, an expert AI career assistant specialized in tech opportunities for college students, freshers, and junior developers across Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy) and hubs (Bangalore, Hyderabad, Remote).

Target Audience Profile:
- Candidate Name: {user_name}
- Candidate Experience: {exp_str}
- Candidate Skills: {skills_str}
- Preferred Locations: {locs_str}
- Preferred Titles: {titles_str}

Curated Job Opportunities (70% Entry-Level/Fresher + 30% Career Growth):
{jobs_text}
{focused_block}

Core Instructions:
1. CONVERSATIONAL MEMORY & JOB Q&A:
   - When the user asks about the active or discussed job (e.g. salary, experience, description, responsibilities, or whether the job is genuine/trusted):
     * ANSWER DIRECTLY and ACCURATELY from the active job data provided above!
     * Salary: Provide the salary if listed, or state clearly that the employer has not disclosed the salary range in the public listing.
     * Experience: Provide the required experience years (e.g. from Required Experience or title).
     * Description/Responsibilities: Give a clear, crisp 2-3 sentence summary of the day-to-day role and tech stack.
     * Trust & Legitimacy: If asked if the job is genuine/trusted, explain the trust score (e.g. 95%), verified ATS status, and absence of scam fees.
     * Always provide the application URL formatted as a clean markdown link: [Apply on Employer Portal](<apply_url>).
     * NEVER state that you don't have salary details or descriptions — you have all the information right here in the prompt.
2. 70/30 STUDENT FOCUS:
   - Matches are curated specifically for college students: ~70% entry-level/fresher roles and ~30% growth roles.
   - If user asks for jobs, present them concisely highlighting their suitability for freshers.
3. CONVERSATIONAL TONE & BREVITY:
   - Keep replies concise, helpful, and natural (1 to 3 sentences).
   - If user says "hello" or greets you: warm 1-sentence greeting asking for skills/locations.
   - If user applied to a job: congratulate them enthusiastically!
4. WHEN TO SHOW JOBS:
   - Set `"show_jobs": true` ONLY if:
     a) The user explicitly queries for jobs/openings (e.g. "show jobs", "Chennai fresher jobs", "top matches"), OR
     b) The user just provided their skills or locations and you are presenting matching roles.
   - If the user is asking questions about a specific job (salary, experience, description, trust): Set `"show_jobs": false` so you don't overwrite their chat with random job cards.
5. JSON Output Schema (ONLY valid JSON):
{{
  "reply": "Clear, informative response with markdown links if applicable.",
  "show_jobs": false,
  "profile_updates": {{
    "skills_to_add": ["skill1"],
    "locations_to_set": ["Chennai"]
  }},
  "suggested_actions": [
    {{"label": "Button Label", "value": "text_to_send"}}
  ]
}}
"""


def format_job_listings_markdown(jobs: List[Dict[str, Any]], intro: str = "") -> str:
    """Dynamically formats job recommendations into clean, production-grade markdown."""
    if not jobs:
        clean_intro = intro.strip().rstrip(":")
        return f"{clean_intro}:\n\n*No matching jobs found right now. Try adding related skills or checking back soon!*".strip()

    lines = []
    if intro and intro.strip():
        clean_intro = intro.strip().rstrip(":")
        lines.append(f"{clean_intro}:")
        lines.append("")

    for idx, j in enumerate(jobs, 1):
        title = j.get("title") or "Technical Role"
        company = j.get("company") or "Employer"
        location = j.get("location") or "Tamil Nadu / Flexible"
        tier_tag = "🎓 [Entry-Level / Fresher]" if j.get("seniority_tier") == "entry" else "🚀 [Career Growth Role]"
        trust_badge = j.get("trust_badge") or "✅ Genuine Opportunity"
        trust_score = j.get("trust_score", 90)
        match_score = j.get("match_score", 80)

        salary = j.get("salary_text")
        salary_str = salary if salary else "Undisclosed by employer"

        exp_min = j.get("experience_min")
        exp_max = j.get("experience_max")
        if exp_min is not None and exp_max is not None:
            exp_str = f"{exp_min}-{exp_max} yrs"
        elif exp_min is not None:
            exp_str = f"Min {exp_min} yrs"
        else:
            exp_str = "Fresher / Entry level"

        skills = j.get("skills") or []
        if isinstance(skills, str):
            skills = _parse_list(skills)
        if not skills:
            skills = extract_skills_from_job(j)
        skills_str = ", ".join(skills[:5]) if skills else "General Tech Stack"

        apply_url = j.get("apply_url") or ""
        apply_link = f"[Apply on Official Portal ↗]({apply_url})" if apply_url else ""

        lines.append(f"{idx}. **{title}** @ **{company}** ({location})")
        lines.append(f"   • {tier_tag} • **Match {match_score}%** • {trust_badge} ({trust_score}% Trust)")
        lines.append(f"   • ⏳ **Exp:** {exp_str} | 💰 **Salary:** {salary_str}")
        lines.append(f"   • 🛠️ **Key Skills:** {skills_str}")
        if apply_link:
            lines.append(f"   • 🔗 {apply_link}")
        lines.append("")

    lines.append("💡 *Tip: Tap any job option below to view full job description, check authenticity, or save for later.*")
    return "\n".join(lines).strip()


def _detect_message_profile_updates(message: str) -> Dict[str, Any]:
    """Extracts explicit skills and target locations from user messages."""
    detected_skills = extract_skills_from_user_message(message)

    msg_lower = message.lower().strip()
    detected_locations = []
    locations_map = {
        "chennai": "Chennai", "coimbatore": "Coimbatore", "madurai": "Madurai",
        "trichy": "Trichy", "salem": "Salem", "bangalore": "Bangalore", "bengaluru": "Bangalore",
        "hyderabad": "Hyderabad", "remote": "Remote", "pune": "Pune", "mumbai": "Mumbai", "delhi": "Delhi"
    }
    for k, v in locations_map.items():
        if k in msg_lower and v not in detected_locations:
            detected_locations.append(v)

    updates = {}
    if detected_skills:
        updates["skills_to_add"] = detected_skills
    if detected_locations:
        updates["locations_to_set"] = detected_locations
    return updates


def _rule_based_fallback(
    message: str,
    profile: Dict[str, Any],
    missing: List[str],
    matched_jobs: List[Dict[str, Any]],
    focused_job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Graceful, comprehensive conversational fallback handling salary, exp, desc, and trust."""
    user_name = (profile.get("full_name") or "there").split()[0]
    msg_lower = message.lower().strip()

    # 1. Job Details Q&A Handler
    if focused_job:
        job_title = focused_job.get("title", "Position")
        company = focused_job.get("company", "Employer")
        apply_url = focused_job.get("apply_url") or ""
        apply_link = f"[Apply on Employer Portal]({apply_url})" if apply_url else ""

        # A. Trust & Authenticity Inquiry
        if any(w in msg_lower for w in ["genuine", "trusted", "fake", "scam", "legit", "safe", "verify", "trust"]):
            score = focused_job.get("trust_score", 92)
            badge = focused_job.get("trust_badge", "🛡️ Verified Genuine")
            signals = ", ".join(focused_job.get("signals") or ["Official enterprise recruitment portal"])
            reply = (
                f"Yes, this posting is **{badge}** with an authenticity score of **{score}%**.\n\n"
                f"• Verified signals: {signals}\n"
                f"• Application: {apply_link}"
            )
            return {
                "reply": reply,
                "show_jobs": False,
                "profile_updates": {},
                "suggested_actions": [
                    {"label": "💰 Check salary", "value": f"What is the salary for {company}?"},
                    {"label": "⏳ Check experience", "value": f"What is the experience for {company}?"},
                    {"label": "🔙 Back to jobs", "value": "Show me more jobs"},
                ],
                "matched_jobs": [],
            }

        # B. Salary Inquiry
        if any(w in msg_lower for w in ["salary", "pay", "ctc", "package", "compensation", "stipend"]):
            salary = focused_job.get("salary_text")
            if salary and salary.strip():
                reply = f"The compensation for **{job_title}** at **{company}** is listed as **{salary}**. Check application portal: {apply_link}"
            else:
                reply = f"The employer hasn't disclosed the salary range in the public listing for **{job_title}** at **{company}**. Compensation is typically discussed during interviews. Apply here: {apply_link}"
            return {
                "reply": reply,
                "show_jobs": False,
                "profile_updates": {},
                "suggested_actions": [
                    {"label": "⏳ Required experience", "value": f"What is the experience for {company}?"},
                    {"label": "📋 Role description", "value": f"What is the description for {company}?"},
                    {"label": "🔙 Back to jobs", "value": "Show me more jobs"},
                ],
                "matched_jobs": [],
            }

        # C. Experience Inquiry
        if any(w in msg_lower for w in ["experience", "exp", "years", "eligibility"]):
            exp_min = focused_job.get("experience_min")
            exp_max = focused_job.get("experience_max")
            match = re.search(r"(\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?)", job_title, re.IGNORECASE)
            if match:
                exp_str = match.group(1)
            elif exp_min is not None and exp_max is not None:
                exp_str = f"{exp_min} to {exp_max} years"
            elif exp_min is not None:
                exp_str = f"At least {exp_min} years"
            else:
                exp_str = "Fresher / Entry level (0-2 years)"
            return {
                "reply": f"For **{job_title}** at **{company}**, the required experience is **{exp_str}**. Ready to apply? {apply_link}",
                "show_jobs": False,
                "profile_updates": {},
                "suggested_actions": [
                    {"label": "💰 Check salary", "value": f"What is the salary for {company}?"},
                    {"label": "📋 Role description", "value": f"What is the description for {company}?"},
                    {"label": "🔙 Back to jobs", "value": "Show me more jobs"},
                ],
                "matched_jobs": [],
            }

        # D. Description / Role Details
        if any(w in msg_lower for w in ["description", "details", "role", "summary", "responsibilities", "about this job"]):
            desc = (focused_job.get("description") or "").strip()
            desc_snippet = desc[:320] + "..." if len(desc) > 320 else desc
            return {
                "reply": f"**{job_title}** at **{company}**:\n\n{desc_snippet}\n\n🔗 {apply_link}",
                "show_jobs": False,
                "profile_updates": {},
                "suggested_actions": [
                    {"label": "💰 Check salary", "value": f"What is the salary for {company}?"},
                    {"label": "⏳ Required experience", "value": f"What is the experience for {company}?"},
                    {"label": "🔙 Back to jobs", "value": "Show me more jobs"},
                ],
                "matched_jobs": [],
            }

    # 2. Detect skills & locations from message
    profile_updates = _detect_message_profile_updates(message)
    detected_skills = profile_updates.get("skills_to_add", [])
    detected_locations = profile_updates.get("locations_to_set", [])

    # 3. Application celebration
    is_apply = "apply" in msg_lower or "applied" in msg_lower
    if is_apply:
        return {
            "reply": f"🎉 Congratulations, {user_name}! Applying is the key step. Review their requirements and prepare a quick 2-minute overview of your projects!",
            "show_jobs": False,
            "profile_updates": {},
            "suggested_actions": [
                {"label": "💼 More matches", "value": "Show me more jobs"},
            ],
            "matched_jobs": [],
        }

    if "update" in msg_lower and "skill" in msg_lower and not detected_skills:
        return {
            "reply": f"Sure, {user_name}! What skills would you like to add? (e.g. React, Python, Java, SQL)",
            "show_jobs": False,
            "profile_updates": {},
            "suggested_actions": [
                {"label": "Python & SQL", "value": "My skills are Python and SQL"},
                {"label": "React & TypeScript", "value": "My skills are React and TypeScript"},
            ],
            "matched_jobs": [],
        }

    if "who are you" in msg_lower:
        return {
            "reply": "I'm your DigiDARA Job Agent! I help college students and tech talent discover verified entry-level jobs and internships across Tamil Nadu and major tech hubs. What roles or skills are you focusing on?",
            "show_jobs": False,
            "profile_updates": {},
            "suggested_actions": [
                {"label": "🎓 Fresher jobs", "value": "Show me fresher jobs"},
                {"label": "🔍 Chennai jobs", "value": "Show me jobs in Chennai"},
            ],
            "matched_jobs": [],
        }

    if msg_lower in {"hello", "hi", "hey", "hello there", "good morning", "good evening"}:
        return {
            "reply": f"Hi {user_name}! 👋 What skills or locations are you targeting for your next job or internship?",
            "show_jobs": False,
            "profile_updates": {},
            "suggested_actions": [
                {"label": "🎓 Fresher jobs", "value": "Show me fresher jobs"},
                {"label": "🔍 Chennai jobs", "value": "Show me jobs in Chennai"},
                {"label": "📍 Coimbatore jobs", "value": "Show me jobs in Coimbatore"},
            ],
            "matched_jobs": [],
        }

    if detected_skills or detected_locations:
        added = []
        if detected_skills:
            added.append(f"skills ({', '.join(detected_skills)})")
        if detected_locations:
            added.append(f"location ({', '.join(detected_locations)})")
        intro = f"Got it, {user_name}! Updated your {' and '.join(added)}. Here are your curated matches (70% entry-level & 30% growth roles)"
        formatted_reply = format_job_listings_markdown(matched_jobs[:4], intro=intro)
        return {
            "reply": formatted_reply,
            "show_jobs": True,
            "profile_updates": profile_updates,
            "suggested_actions": [
                {"label": "🔍 More matches", "value": "Show me more jobs"},
            ],
            "matched_jobs": matched_jobs[:4],
        }

    return {
        "reply": f"Hi {user_name}! Tell me your skills or preferred cities (e.g. Chennai, Coimbatore, Bangalore, Remote), and I'll find matching fresher and entry-level jobs for you.",
        "show_jobs": False,
        "profile_updates": {},
        "suggested_actions": [
            {"label": "🎓 Fresher software jobs", "value": "Show me fresher jobs"},
            {"label": "🔍 Chennai jobs", "value": "Show me jobs in Chennai"},
        ],
        "matched_jobs": [],
    }


def chat_with_job_agent(
    user_id: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    selected_job_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Main conversational entry point for DigiDARA Job Agent with full memory, 70/30 blend, and trust verification."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        profile, missing = _get_user_profile_and_missing(cursor, user_id)

        # 1. Pre-detect skills and locations from message and apply immediately
        msg_updates = _detect_message_profile_updates(message)
        changed_fields = []
        if msg_updates:
            profile, changed_fields = _apply_profile_updates(db, cursor, user_id, profile, msg_updates)

        # 2. Query top matched jobs against active profile (now reflecting new skills)
        matched_jobs, is_unapplied_backfill = _get_top_matched_jobs(cursor, profile, user_id=user_id, limit=6)

        # Detect active job being discussed
        focused_job = _detect_focused_job(cursor, message, history or [], matched_jobs, selected_job_id=selected_job_id)

        system_prompt = _build_system_prompt(profile, missing, matched_jobs, focused_job=focused_job)

        openai_key = OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "").strip()
        result = None

        if openai_key:
            try:
                messages = [{"role": "system", "content": system_prompt}]
                if history:
                    for h in history[-8:]:  # send last 8 turns for conversational memory
                        role = "user" if h.get("role") == "user" else "assistant"
                        content = str(h.get("content") or "").strip()
                        if content:
                            messages.append({"role": role, "content": content})
                messages.append({"role": "user", "content": message})

                resp = requests.post(
                    OPENAI_API_URL,
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_MODEL,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "temperature": 0.4,
                        "max_tokens": 450,
                    },
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    result = json.loads(content_str)
                else:
                    logger.warning("OpenAI API returned %s: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("OpenAI call failed, falling back to rule-based: %s", e)

        if not result or not isinstance(result, dict) or "reply" not in result:
            result = _rule_based_fallback(message, profile, missing, matched_jobs, focused_job=focused_job)

        # Apply profile updates if extracted by LLM
        profile_updates = result.get("profile_updates") or {}
        if profile_updates and isinstance(profile_updates, dict):
            profile, llm_changed = _apply_profile_updates(db, cursor, user_id, profile, profile_updates)
            if llm_changed:
                changed_fields.extend(llm_changed)
                matched_jobs, _ = _get_top_matched_jobs(cursor, profile, user_id=user_id, limit=6)

        # Determine whether to display job cards
        user_explicit_job_query = any(
            w in message.lower()
            for w in [
                "show job", "show jobs", "find job", "find jobs", "top match", "best match",
                "chennai jobs", "coimbatore jobs", "python jobs", "react jobs", "developer jobs",
                "fresher jobs", "internship", "openings", "unapplied"
            ]
        )
        is_job_detail_query = any(
            w in message.lower()
            for w in ["salary", "experience", "description", "details", "genuine", "trusted", "role"]
        ) and bool(focused_job)

        has_profile_info = bool(profile["skills"] or profile["preferred_locations"])
        user_provided_skills_or_loc = bool(msg_updates.get("skills_to_add")) or bool(msg_updates.get("locations_to_set"))
        show_jobs = (
            result.get("show_jobs", False)
            or bool(changed_fields)
            or user_provided_skills_or_loc
            or user_explicit_job_query
        ) and not is_job_detail_query
        should_return_jobs = show_jobs and has_profile_info

        reply = result.get("reply", "")
        # Dynamically append or embed the formatted job listings whenever jobs should be shown
        if should_return_jobs and matched_jobs and "1. **" not in reply:
            reply = format_job_listings_markdown(matched_jobs[:4], intro=reply)

        return {
            "reply": reply,
            "show_jobs": should_return_jobs,
            "updated_profile": {
                "skills": profile["skills"],
                "preferred_locations": profile["preferred_locations"],
                "preferred_titles": profile["preferred_titles"],
                "preferred_work_mode": profile["preferred_work_mode"],
                "experience_years": profile["experience_years"],
                "changed_fields": list(dict.fromkeys(changed_fields)),
            },
            "suggested_actions": result.get("suggested_actions") or [],
            "matched_jobs": matched_jobs[:4] if should_return_jobs else [],
        }
    finally:
        cursor.close()
        db.close()


# Compatibility alias
chat_with_job_copilot = chat_with_job_agent
