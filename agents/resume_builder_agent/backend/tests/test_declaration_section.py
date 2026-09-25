from copy import deepcopy
from io import BytesIO
from pypdf import PdfReader
import pytest

from app import create_app, db
from app.models import Resume, User
from app.services import pdf_export
from app.services.import_review import map_import_to_resume_payload


STANDARD_DECLARATION = (
    "I hereby declare that the information provided in this resume is true "
    "and accurate to the best of my knowledge and belief."
)


def sample_payload():
    return {
        "title": "Software Engineer Resume",
        "target_role": "Python Developer",
        "summary": "Experienced backend developer specializing in Python and APIs.",
        "personal_info": {
            "name": "Alex Smith",
            "email": "alex@example.com",
            "phone": "+1 555 1234",
            "location": "New York, NY",
            "links": ["GitHub: github.com/alexsmith"],
        },
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Software Engineer",
                "start_date": "2022-01-01",
                "end_date": "2024-01-01",
                "ai_generated_bullets": ["Built Python microservices for high-volume transactions."],
            }
        ],
        "education": [
            {
                "school": "University of Tech",
                "degree": "B.S.",
                "field": "Computer Science",
                "start_date": "2018",
                "end_date": "2022",
            }
        ],
        "skills": [{"skill_name": "Python"}, {"skill_name": "FastAPI"}, {"skill_name": "PostgreSQL"}],
        "projects": [],
        "certifications": [],
        "languages": [],
        "publications": [],
        "achievements": [],
    }


def extract_pdf_text(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_pdf_default_standard_declaration():
    payload = deepcopy(sample_payload())
    payload["declaration"] = STANDARD_DECLARATION
    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" in text.upper()
    assert STANDARD_DECLARATION in text or "true and accurate to the best of my knowledge" in text
    assert "Arun Kuma" not in text
    assert "Chennai" not in text
    assert "DD/MM/YYYY" not in text


def test_pdf_omitted_declaration_does_not_render():
    payload = deepcopy(sample_payload())
    # No declaration provided -> omitted cleanly
    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" not in text.upper()
    assert "Arun Kuma" not in text


def test_pdf_custom_declaration():
    payload = deepcopy(sample_payload())
    payload["declaration"] = "I confirm that all statements made in this document are authentic and verified."
    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" in text.upper()
    assert "authentic and verified" in text
    assert "Arun Kuma" not in text


def test_pdf_disabled_declaration():
    payload = deepcopy(sample_payload())
    payload["declaration_enabled"] = False
    payload["declaration"] = STANDARD_DECLARATION

    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" not in text.upper()
    assert "true and accurate" not in text


def test_pdf_empty_declaration():
    payload = deepcopy(sample_payload())
    payload["declaration"] = "   "

    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" not in text.upper()


def test_pdf_placeholder_declaration_not_rendered():
    for placeholder in ["[Add declaration statement]", "None", "null", "N/A", "undefined"]:
        payload = deepcopy(sample_payload())
        payload["declaration"] = placeholder

        pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
        text = extract_pdf_text(pdf_bytes)

        assert placeholder not in text
        assert "DECLARATION" not in text.upper()


def test_navy_portrait_renders_declaration():
    payload = deepcopy(sample_payload())
    payload["declaration"] = STANDARD_DECLARATION
    payload["declaration_enabled"] = True

    pdf_bytes = pdf_export.render_resume_pdf(payload, "navy-portrait")
    text = extract_pdf_text(pdf_bytes)

    assert "DECLARATION" in text.upper()
    assert "true and accurate" in text

    # Also test when disabled
    payload["declaration_enabled"] = False
    pdf_bytes_disabled = pdf_export.render_resume_pdf(payload, "navy-portrait")
    text_disabled = extract_pdf_text(pdf_bytes_disabled)
    assert "DECLARATION" not in text_disabled.upper()


def test_all_major_templates_render_declaration_cleanly():
    templates = [
        "steady-form",
        "classic-serif",
        "mercury-flow",
        "slate-dawn",
        "navy-portrait",
        "ats-standard",
        "analyst-pro",
    ]
    for template_id in templates:
        payload = deepcopy(sample_payload())
        payload["declaration"] = STANDARD_DECLARATION
        payload["declaration_enabled"] = True

        pdf_bytes = pdf_export.render_resume_pdf(payload, template_id)
        assert len(pdf_bytes) > 0, f"Failed generating PDF for template {template_id}"
        text = extract_pdf_text(pdf_bytes)
        assert "DECLARATION" in text.upper(), f"Template {template_id} missing declaration"


def test_import_mapping_omits_declaration_if_not_present():
    parsed = {
        "personal_info": {"name": "Test User"},
        "education": [],
        "experience": [],
        "skills": [],
    }
    payload = map_import_to_resume_payload(parsed, "resume.pdf", "user-123")
    # declaration_enabled should be False when no declaration in imported document
    assert payload.get("declaration_enabled") is False

    # When imported document does have a declaration
    parsed_with_dec = {
        **parsed,
        "declaration": "I hereby declare that this resume is accurate.",
    }
    payload_with_dec = map_import_to_resume_payload(parsed_with_dec, "resume.pdf", "user-123")
    assert payload_with_dec.get("declaration_enabled") is True
    assert payload_with_dec.get("declaration") == "I hereby declare that this resume is accurate."


def test_resumes_api_declaration_persistence(client, sample_resume_payload):
    payload = {
        **sample_resume_payload,
        "declaration": STANDARD_DECLARATION,
        "declaration_enabled": True,
    }
    create_res = client.post("/api/resume", json=payload, headers={"X-User-Id": "test-user"})
    assert create_res.status_code == 201
    created = create_res.get_json()["data"]
    resume_id = created["id"]
    assert created.get("declaration_enabled") is True
    assert created.get("declaration") == STANDARD_DECLARATION

    # Now update: disable declaration
    update_payload = {
        **payload,
        "declaration_enabled": False,
        "declaration": "",
    }
    put_res = client.put(f"/api/resume/{resume_id}", json=update_payload, headers={"X-User-Id": "test-user"})
    assert put_res.status_code == 200
    updated = put_res.get_json()["data"]
    assert updated.get("declaration_enabled") is False
    assert updated.get("declaration") in ("", None)

    # Fetch and verify persisted in DB
    get_res = client.get(f"/api/resume/{resume_id}", headers={"X-User-Id": "test-user"})
    assert get_res.status_code == 200
    fetched = get_res.get_json()["data"]
    assert fetched.get("declaration_enabled") is False
    assert fetched.get("declaration") in ("", None)


def test_ai_generate_declaration_returns_standard_neutral(client):
    res = client.post("/api/ai/generate-declaration", json={"name": "Jane Doe", "target_role": "Developer"})
    assert res.status_code == 200
    data = res.get_json()
    declaration = data["declaration"]
    assert "true and accurate" in declaration or "true and correct" in declaration
    assert "Arun Kuma" not in declaration
    assert "Chennai" not in declaration
    assert "DD/MM/YYYY" not in declaration

