from datetime import date

from app.services.ats_scoring import analyze_resume, estimate_years, normalize_skill


BASE_RESUME = {
    "personalInfo": {
        "fullName": "Alex Morgan",
        "email": "alex@example.com",
        "phone": "+1 555 123 4567",
        "location": "Remote",
    },
    "targetRole": "Data Analyst",
    "summary": "Data Analyst with Python, SQL, and Power BI dashboard experience.",
    "skills": [{"skill_name": "Python, SQL, Power BI"}],
    "experience": [{
        "company": "Acme",
        "role": "Data Analyst",
        "start_date": "2022",
        "end_date": "2024",
        "raw_input": "Built Power BI dashboards with SQL and Python for KPI reporting.",
        "ai_generated_bullets": [],
    }],
    "education": [{"school": "State University", "degree": "Bachelor", "field": "Computer Science"}],
    "projects": [{"title": "Sales Dashboard", "description": "Created a Power BI dashboard using SQL."}],
    "certifications": [],
    "languages": [],
}


def test_same_inputs_return_same_score():
    jd = "Role: Data Analyst\nRequired: Python, SQL, PowerBI\nPreferred: Tableau\n2+ years experience"
    first = analyze_resume(BASE_RESUME, str(BASE_RESUME), jd)
    second = analyze_resume(BASE_RESUME, str(BASE_RESUME), jd)

    assert first["score"]["normalized_score"] == second["score"]["normalized_score"]
    assert first["breakdown"] == second["breakdown"]


def test_skill_normalization_and_synonyms():
    assert normalize_skill("PowerBI") == "Power BI"
    assert normalize_skill("MS Power BI") == "Power BI"
    assert normalize_skill("SKLearn") == "scikit-learn"
    assert normalize_skill("React.js") == "React"


def test_unsafe_substring_matching_is_prevented():
    resume = {**BASE_RESUME, "skills": [{"skill_name": "React"}]}
    jd = "Required: R, C"
    analysis = analyze_resume(resume, str(resume), jd)
    matched = [item["skill"] for item in analysis["skills"]["matched_required"]]

    assert "R" not in matched
    assert "C" not in matched


def test_required_preferred_weighting_and_evidence():
    jd = "Required: Python, SQL, PostgreSQL\nPreferred: PowerBI, Tableau"
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), jd)

    skills = analysis["skills"]
    assert {item["skill"] for item in skills["matched_required"]} == {"Python", "SQL"}
    assert {item["skill"] for item in skills["missing_required"]} == {"PostgreSQL"}
    assert {item["skill"] for item in skills["matched_preferred"]} == {"Power BI"}
    assert skills["matched_required"][0]["evidence"]


def test_resume_only_quality_mode_is_not_job_match():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "")

    assert analysis["analysis_type"] == "resume_quality"
    assert analysis["jobMatch"] is None
    assert analysis["requirements"] == []


def test_missing_education_requirement_is_not_zero_penalty():
    jd = "Required: Python, SQL\nResponsibilities: build dashboards"
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), jd)

    education = analysis["breakdown"]["education_certifications"]
    assert education["applicable"] is False


def test_experience_years_ignore_education_dates_and_sum_internship_duration():
    # The education history spans 2020-2026, but the only work interval is a
    # three-month internship. estimate_years receives only Experience text.
    full_resume_text = "SSC 2020\nJunior College 2022\nB.Tech expected 2026"
    experience_text = "AI Engineer Intern | Jun 2024 - Aug 2024 | Built ML evaluation tools."

    assert estimate_years(experience_text, today=date(2026, 8, 1)) == 0.25
    assert estimate_years("Engineer | 2024-06-01 - 2024-08-31", today=date(2026, 8, 1)) == 0.25
    resume = {
        **BASE_RESUME,
        "experience": [{
            "company": "Acme", "role": "AI Engineer Intern",
            "raw_input": experience_text,
        }],
        "education": [{"school": "University", "degree": "B.Tech 2022 - 2026"}],
    }
    analysis = analyze_resume(resume, f"{full_resume_text}\n{experience_text}", "Role: AI Engineer\n2 years experience")

    assert "Detected about 0.2 years" in analysis["breakdown"]["experience"]["explanation"]


def test_saved_experience_dates_are_scored_as_a_range_not_unrelated_years():
    resume = {
        **BASE_RESUME,
        "experience": [{
            "company": "Acme", "role": "Intern",
            "start_date": "2024-06-01", "end_date": "2024-08-31",
            "raw_input": "Supported reporting work.",
        }],
        "education": [{"school": "University", "degree": "B.Tech 2020 - 2026"}],
    }
    analysis = analyze_resume(resume, "Education 2020 - 2026", "Role: Analyst\n2 years experience")

    assert "Detected about 0.2 years" in analysis["breakdown"]["experience"]["explanation"]
    assert estimate_years("Internship 2020 Education 2025") == 0


def test_completeness_names_the_missing_section_instead_of_generic_advice():
    resume = {**BASE_RESUME, "summary": ""}
    analysis = analyze_resume(resume, str(resume), "Role: Analyst")
    completeness = analysis["breakdown"]["completeness"]

    assert completeness["earned"] == 8
    assert "professional summary" in completeness["explanation"]
    assert "professional summary" in completeness["improvement_action"]


def test_target_role_is_used_when_job_description_is_empty():
    without_target = analyze_resume(BASE_RESUME, str(BASE_RESUME), "")
    with_target = analyze_resume(BASE_RESUME, str(BASE_RESUME), "", target_role="AI Engineer")

    assert without_target["analysis_type"] == "resume_quality"
    assert with_target["analysis_type"] == "job_match"
    assert with_target["score"]["normalized_score"] != without_target["score"]["normalized_score"]


def test_inapplicable_categories_are_labeled_not_applicable_in_all_outputs():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "Required: Python")

    education = analysis["breakdown"]["education_certifications"]
    assert education["applicable"] is False
    assert education["status"] == "Not Applicable"
    category = next(item for item in analysis["categories"] if item["category"] == "Education and Certifications")
    assert category["status"] == "Not Applicable"
    assert category["recommendedAction"] is None


def test_short_role_title_does_not_create_a_false_critical_skills_score():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "Data Analyst")
    skills = analysis["breakdown"]["skills"]
    category = next(item for item in analysis["categories"] if item["category"] == "Skills Match")

    assert skills["applicable"] is False
    assert skills["status"] == "Not Applicable"
    assert category["status"] == "Not Applicable"
    assert "fuller job description" in skills["explanation"]


def test_role_and_skills_only_prompt_does_not_create_a_false_critical_context_score():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "Role: Data Analyst\nRequired: Python, SQL")
    context = analysis["breakdown"]["context_relevance"]

    assert context["applicable"] is False
    assert context["status"] == "Not Applicable"
    assert "actual responsibilities" in context["explanation"]


def test_short_actionable_responsibility_is_still_scored_for_context():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "Role: Data Analyst\nResponsibilities: Build dashboards")
    context = analysis["breakdown"]["context_relevance"]

    assert context["applicable"] is True
    assert context["status"] != "Not Applicable"


def test_experience_without_minimum_years_is_explained_as_title_only():
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), "Role: Data Analyst")
    experience = analysis["breakdown"]["experience"]

    assert "No minimum years were specified" in experience["explanation"]
    assert "Detected about" not in experience["explanation"]


def test_marketing_skills_are_matched_from_expanded_vocabulary():
    marketing_resume = {
        **BASE_RESUME,
        "summary": "Digital marketer specializing in SEO, Google Analytics, and campaign management.",
        "skills": [{"skill_name": "SEO, Google Analytics, Campaign Management, Content Marketing"}],
        "experience": [{
            "company": "Growth Co", "role": "Marketing Specialist",
            "raw_input": "Managed SEO campaigns and used Google Analytics to improve acquisition.",
        }],
    }
    analysis = analyze_resume(
        marketing_resume, str(marketing_resume),
        "Required: SEO, Google Analytics, Campaign Management",
    )

    skills = analysis["skills"]
    assert {item["skill"] for item in skills["matched_required"]} == {
        "SEO", "Google Analytics", "Campaign Management",
    }
    assert analysis["breakdown"]["skills"]["earned"] == 24


def test_detailed_genuine_skill_mismatch_remains_critical():
    analysis = analyze_resume(
        BASE_RESUME, str(BASE_RESUME),
        "Required: SEO, Google Analytics, Campaign Management",
    )

    skills = analysis["breakdown"]["skills"]
    assert skills["applicable"] is True
    assert skills["earned"] == 0
    assert skills["status"] == "Critical"
    assert {item["skill"] for item in analysis["skills"]["missing_required"]} == {
        "SEO", "Google Analytics", "Campaign Management",
    }


def test_score_boundaries_and_breakdown_range():
    jd = "Required: Python, SQL, PowerBI"
    analysis = analyze_resume(BASE_RESUME, str(BASE_RESUME), jd)
    score = analysis["score"]["normalized_score"]

    assert 0 <= score <= 100
    assert analysis["score"]["classification"] in {
        "Excellent Match",
        "Strong Match",
        "Moderate Match",
        "Weak Match",
        "Low Match",
    }
