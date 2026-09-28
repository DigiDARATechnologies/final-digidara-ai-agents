"""
Test suite validating the 4 specific QA issues and enhancements:
1. AI making assumptions about user information (M.E. false positives, degree as name).
2. Job verification transparency & removal of Greenhouse/Lever/Workday (Adzuna & RapidAPI JSearch).
3. Smarter Job Matching (Match %, matching_skills, missing_skills, preparation_tips).
4. Strict location filtering ("Show me a chennai jobs" excludes Coimbatore).
"""

from unittest.mock import MagicMock
import pytest

try:
    from job_agent.chat_service import (
        extract_education_from_text,
        _detect_name_from_message,
        _is_valid_human_name,
        _matches_location_filter,
        _get_top_matched_jobs,
        format_job_listings_markdown,
    )
    from job_agent.trust import (
        evaluate_job_trust,
        ADZUNA_DOMAINS,
        RAPIDAPI_DOMAINS,
    )
    from job_agent.matching import score_job
except ModuleNotFoundError:
    from agents.job_agent.chat_service import (
        extract_education_from_text,
        _detect_name_from_message,
        _is_valid_human_name,
        _matches_location_filter,
        _get_top_matched_jobs,
        format_job_listings_markdown,
    )
    from agents.job_agent.trust import (
        evaluate_job_trust,
        ADZUNA_DOMAINS,
        RAPIDAPI_DOMAINS,
    )
    from agents.job_agent.matching import score_job


# ==============================================================================
# ISSUE 1: False Assumptions & Candidate Name Validation
# ==============================================================================

def test_extract_education_no_false_me_or_it():
    # Ordinary conversational phrases with "me", "be", "it" should NOT extract M.E, B.E, or IT
    assert extract_education_from_text("Can you show me jobs?") is None
    assert extract_education_from_text("help me find a job") is None
    assert extract_education_from_text("will it be good for freshers?") is None
    assert extract_education_from_text("tell me about the company") is None


def test_extract_education_valid_degrees():
    # Legitimate degree mentions should extract cleanly
    res_be = extract_education_from_text("I completed B.E. in Computer Science")
    assert res_be is not None
    assert "B.E" in res_be
    assert "Computer Science" in res_be

    res_me = extract_education_from_text("I have an M.E. in VLSI Design")
    assert res_me is not None
    assert "M.E" in res_me

    res_btech = extract_education_from_text("Graduated with B.Tech Information Technology")
    assert res_btech is not None
    assert "B.Tech" in res_btech
    assert "Information Technology" in res_btech


def test_candidate_name_rejection_of_degrees_and_questions():
    # Education degrees and academic phrases must NOT be treated as a user's name
    assert not _is_valid_human_name("B.Tech Computer Science")
    assert not _is_valid_human_name("Master of Engineering")
    assert not _is_valid_human_name("B.E.")
    assert not _is_valid_human_name("BSc Information Technology")

    # Questions and greetings must NOT be treated as a user's name
    assert not _is_valid_human_name("Can you help me find jobs?")
    assert not _is_valid_human_name("What is your purpose?")
    assert not _is_valid_human_name("How are you?")
    assert not _is_valid_human_name("Hello there")

    # Valid human names must be accepted
    assert _is_valid_human_name("Rajesh Kumar")
    assert _is_valid_human_name("Priya S")
    assert _is_valid_human_name("Anand Ramesh")

    assert _detect_name_from_message("My name is Rajesh Kumar") == "Rajesh Kumar"
    assert _detect_name_from_message("I am Priya S") == "Priya S"
    assert _detect_name_from_message("Can you help me?") is None
    assert _detect_name_from_message("B.Tech Computer Science") is None


def test_candidate_name_rejection_of_keyboard_mash_and_gibberish():
    # Keyboard mash sequences must be rejected
    assert not _is_valid_human_name("wertyui")
    assert not _is_valid_human_name("qwerty")
    assert not _is_valid_human_name("asdfgh")
    assert not _is_valid_human_name("zxcvbn")
    assert not _is_valid_human_name("poiuyt")
    assert not _is_valid_human_name("lkjhgf")

    # Character repetition spam must be rejected
    assert not _is_valid_human_name("aaaaa")
    assert not _is_valid_human_name("zzzz")
    assert not _is_valid_human_name("asdasdasd")

    # Consonant-only gibberish must be rejected
    assert not _is_valid_human_name("bcdfgh")
    assert not _is_valid_human_name("dfgh")

    # Name detection should return None for mash
    assert _detect_name_from_message("wertyui") is None
    assert _detect_name_from_message("My name is wertyui") is None
    assert _detect_name_from_message("I am asdfgh") is None


# ==============================================================================
# ISSUE 2: Transparent Verification & Removal of Greenhouse/Lever/Workday
# ==============================================================================

def test_trust_aggregators_transparent_badges():
    # Adzuna listings get transparent aggregator badge
    adzuna_eval = evaluate_job_trust({
        "title": "Software Engineer",
        "employer_name": "Infosys",
        "company": "Infosys",
        "apply_url": "https://www.adzuna.in/details/12345",
        "source": "adzuna",
        "description": "Enterprise software engineer role with full tech stack responsibilities.",
    })
    assert adzuna_eval["trust_badge"] == "📋 Aggregator Listing (via Adzuna)"
    assert adzuna_eval["trust_level"] == "aggregator"
    assert adzuna_eval["is_verified"] is True  # Verified via API, but clearly badged as aggregator

    # RapidAPI JSearch listings get transparent aggregator badge
    jsearch_eval = evaluate_job_trust({
        "title": "Software Developer",
        "employer_name": "TCS",
        "company": "TCS",
        "apply_url": "https://jsearch.p.rapidapi.com/job/67890",
        "source": "jsearch",
        "description": "Full stack developer role in enterprise IT services with cloud platforms.",
    })
    assert jsearch_eval["trust_badge"] == "📋 Aggregator Listing (via RapidAPI JSearch)"
    assert jsearch_eval["trust_level"] == "aggregator"


def test_trust_corporate_careers_vs_aggregators():
    # Direct company career site is marked as direct employer
    direct_eval = evaluate_job_trust({
        "title": "Software Engineer",
        "company": "Google",
        "apply_url": "https://careers.google.com/jobs/results/123",
        "source": "careers",
        "description": "Work on scalable distributed systems across Google Cloud platform products and tools." * 4,
    })
    assert direct_eval["trust_badge"] == "🏢 Direct Employer Career Page"
    assert direct_eval["trust_level"] == "direct_employer"


def test_greenhouse_lever_workday_completely_cleared():
    try:
        import job_agent.trust as trust_module
    except ModuleNotFoundError:
        import agents.job_agent.trust as trust_module

    # Confirm Greenhouse, Lever, Workday are completely removed from trust module attributes
    assert not hasattr(trust_module, "CORPORATE_ATS_HOSTS")
    assert not hasattr(trust_module, "ALLOWED_ATS_HOSTS")
    assert hasattr(trust_module, "ADZUNA_DOMAINS")
    assert hasattr(trust_module, "RAPIDAPI_DOMAINS")

    # A greenhouse link is now evaluated as a standard web domain, not a hardcoded ATS
    gh_eval = evaluate_job_trust({
        "title": "Backend Developer",
        "company": "Stripe",
        "apply_url": "https://boards.greenhouse.io/stripe/jobs/1",
        "source": "stripe",
        "description": "Backend infrastructure developer role working with payment services." * 4,
    })
    assert gh_eval["trust_badge"] != "🛡️ Verified Corporate Posting"


# ==============================================================================
# ISSUE 3: Smarter Job Matching (Match %, Matching & Missing Skills, Prep Tips)
# ==============================================================================

def test_score_job_enriches_skills_and_prep_tips():
    candidate_profile = {
        "skills": ["Python", "FastAPI", "SQL"],
        "target_locations": ["Chennai"],
        "preferred_locations": ["Chennai"],
        "work_mode": "Hybrid",
        "experience_years": 1,
    }

    job = {
        "id": "job_1",
        "title": "Backend Python Developer",
        "skills": ["python", "fastapi", "docker", "kubernetes", "aws"],
        "location": "Chennai",
        "work_mode": "Hybrid",
        "experience_min": 0,
        "experience_max": 2,
    }

    score, reasons = score_job(job, candidate_profile, course_name="")

    # score_job must mutate job with rich matching metadata
    assert "matching_skills" in job
    assert "missing_skills" in job
    assert "match_percentage" in job
    assert "preparation_tips" in job

    # Check matching & missing skills
    assert "python" in [s.lower() for s in job["matching_skills"]]
    assert "fastapi" in [s.lower() for s in job["matching_skills"]]
    assert "docker" in [s.lower() for s in job["missing_skills"]]
    assert "kubernetes" in [s.lower() for s in job["missing_skills"]]

    # Match % must be between 1 and 100
    assert 1 <= job["match_percentage"] <= 100

    # Prep tip should give guidance on missing skills
    assert len(job["preparation_tips"]) > 0
    assert any(tech in job["preparation_tips"].lower() for tech in ["docker", "kubernetes", "aws", "skill"])


def test_format_job_listings_markdown_renders_rich_match_metadata():
    jobs = [
        {
            "id": "j1",
            "title": "Python Developer",
            "company": "TechCorp",
            "location": "Chennai",
            "skills": ["python", "django", "aws"],
            "matching_skills": ["python"],
            "missing_skills": ["django", "aws"],
            "match_percentage": 78,
            "preparation_tips": "Strengthen Django and AWS to stand out for this role.",
            "source": "adzuna",
            "source_url": "https://adzuna.in/job1",
            "work_mode": "On-site",
        }
    ]

    md = format_job_listings_markdown(jobs)
    assert "**Match 78%**" in md
    assert "✅ **Matched Skills:**" in md
    assert "python" in md.lower()
    assert "⚠️ **Missing Skills:**" in md
    assert "django" in md.lower()
    assert "💡 **Prep Tip:**" in md
    assert "Strengthen Django and AWS" in md


# ==============================================================================
# ISSUE 4: Strict Location Filter (Chennai Query Excludes Coimbatore)
# ==============================================================================

def test_matches_location_filter_logic():
    # Direct match
    assert _matches_location_filter("Chennai, Tamil Nadu", "onsite", ["Chennai"])
    # Remote match
    assert _matches_location_filter("Coimbatore, Tamil Nadu", "remote", ["Chennai"])
    assert _matches_location_filter("Remote, India", "onsite", ["Chennai"])

    # Strict physical mismatch
    assert not _matches_location_filter("Coimbatore, Tamil Nadu", "onsite", ["Chennai"])
    assert not _matches_location_filter("Bengaluru, Karnataka", "hybrid", ["Chennai"])


def test_get_top_matched_jobs_strict_location_excludes_coimbatore():
    sample_jobs = [
        {
            "id": 101,
            "title": "Software Engineer - Chennai",
            "company": "Alpha Tech",
            "location": "Chennai, Tamil Nadu",
            "skills": ["python"],
            "work_mode": "Onsite",
            "experience_min": 0,
            "experience_max": 2,
            "salary_text": None,
            "description": "Chennai software role",
            "category": "Engineering",
            "external_id": "ext1",
            "apply_url": "https://alphatech.com/careers/1",
            "published_at": None,
        },
        {
            "id": 102,
            "title": "Software Engineer - Coimbatore",
            "company": "Beta Tech",
            "location": "Coimbatore, Tamil Nadu",
            "skills": ["python"],
            "work_mode": "Onsite",
            "experience_min": 0,
            "experience_max": 2,
            "salary_text": None,
            "description": "Coimbatore software role",
            "category": "Engineering",
            "external_id": "ext2",
            "apply_url": "https://betatech.com/careers/2",
            "published_at": None,
        },
        {
            "id": 103,
            "title": "Software Engineer - Remote",
            "company": "Gamma Tech",
            "location": "All India",
            "skills": ["python"],
            "work_mode": "Remote",
            "experience_min": 0,
            "experience_max": 2,
            "salary_text": None,
            "description": "Remote software role",
            "category": "Engineering",
            "external_id": "ext3",
            "apply_url": "https://gammatech.com/careers/3",
            "published_at": None,
        },
    ]

    profile = {"skills": ["python"], "preferred_locations": ["Chennai"], "preferred_work_mode": "all"}

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = sample_jobs

    # Strict location search for Chennai
    matched, _ = _get_top_matched_jobs(
        mock_cursor,
        profile,
        limit=10,
        location_filter=["Chennai"],
        strict_location=True,
    )

    matched_ids = [j["id"] for j in matched]
    assert 101 in matched_ids
    assert 103 in matched_ids
    # Coimbatore MUST NOT be in results
    assert 102 not in matched_ids
