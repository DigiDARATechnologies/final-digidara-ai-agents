import json
import pytest
from app.services import import_review
from app.routes import resumes, ai


def test_experience_bullets_exceeding_20_are_normalized_and_capped_without_error(client, sample_resume_payload):
    """Verify experience with >20 bullets is normalized and capped at 20 without failing schema validation."""
    overloaded_bullets = [f"Achieved key performance objective number {i}." for i in range(1, 35)]
    sample_resume_payload["experience"][0]["ai_generated_bullets"] = overloaded_bullets

    res = client.post("/api/resumes", json=sample_resume_payload)
    assert res.status_code == 201
    data = res.get_json()["data"]
    saved_bullets = data["experience"][0]["ai_generated_bullets"]
    assert len(saved_bullets) == 20
    assert saved_bullets[0] == "Achieved key performance objective number 1."
    assert saved_bullets[19] == "Achieved key performance objective number 20."


def test_normalize_experience_bullets_deduplicates_and_cleans_items():
    bullets = [
        " - Built 12 KPI reports.",
        "Built 12 KPI reports.",
        "",
        None,
        "[object Object]",
        "  • Improved reporting speed by 30%.  ",
        "you can improve it later with AI.",
    ]
    cleaned = import_review.normalize_experience_bullets(bullets, max_items=20)
    assert cleaned == [
        "Built 12 KPI reports.",
        "Improved reporting speed by 30%.",
    ]


def test_normalize_target_role_fixes_typos_and_casing():
    assert import_review.normalize_target_role("Digital marketting") == "Digital Marketing"
    assert import_review.normalize_target_role("digital marketing") == "Digital Marketing"
    assert import_review.normalize_target_role("python developer") == "Python Developer"
    assert import_review.normalize_target_role("front end developer") == "Frontend Developer"


def test_short_job_description_does_not_fail_ats_scoring(client, sample_resume_payload):
    res = client.post("/api/resume", json=sample_resume_payload)
    created = res.get_json()["data"]
    resume = resumes.get_resume_or_404(created["id"])
    parsed, plain_text = resumes.resume_to_ats_input(resume)
    result = import_review.score_resume(parsed, [], plain_text, job_description="Digital marketing", target_role="Digital Marketing")
    assert result["score"]["normalized_score"] > 0
    assert result.get("jobMatch") is not None


def test_fresher_level_preserves_existing_experience():
    parsed = {
        "personalInfo": {"fullName": "Jane Doe", "email": "jane@example.com"},
        "targetRole": "Digital Marketing",
        "experience": [
            {"company": "Marketing Corp", "role": "Marketing Intern", "start_date": "2024", "end_date": "2025"}
        ],
        "education": [
            {"school": "State University", "degree": "Bachelor of Business", "level": "UG"}
        ],
    }
    payload = import_review.map_import_to_resume_payload(parsed, "resume.pdf", "user-fresher")
    assert len(payload["experience"]) == 1
    assert payload["experience"][0]["company"] == "Marketing Corp"
    assert len(payload["education"]) == 1
