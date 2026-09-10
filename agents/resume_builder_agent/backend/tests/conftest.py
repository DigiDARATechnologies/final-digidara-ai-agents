import os
from sqlalchemy.engine import make_url

import pytest

from app import create_app
from app.extensions import db



def integration_url(fallback):
    value = os.environ.get("INTEGRATION_DATABASE_URL")
    if not value:
        return fallback
    url = make_url(value)
    if url.get_backend_name() != "mysql" or not (url.database or "").endswith("_test"):
        raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
    return value

@pytest.fixture()
def app(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = "test-secret-key-for-security-regression-tests"
        ALLOW_DEV_USER_HEADER = True
        SQLALCHEMY_DATABASE_URI = integration_url(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_resume_payload():
    return {
        "user_id": "test-user",
        "title": "Software Engineer Resume",
        "template_choice": "steady-form",
        "summary": "Full-stack engineer focused on practical product delivery.",
        "personal_info": {
            "name": "Demo User",
            "email": "demo@example.com",
            "phone": "555-0100",
            "location": "Remote",
            "links": ["https://example.com"],
        },
        "education": [
            {
                "school": "Example University",
                "degree": "BS",
                "field": "Computer Science",
                "start_date": "2020",
                "end_date": "2024",
                "cgpa": "8.7",
            }
        ],
        "experience": [
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "start_date": "2024-01-01",
                "end_date": None,
                "raw_input": "Built internal APIs, dashboards, and workflow tools for operations teams.",
                "ai_generated_bullets": [
                    "Built internal APIs and dashboards that improved operational visibility."
                ],
            }
        ],
        "skills": [{"skill_name": "Python"}, {"skill_name": "React"}],
        "certifications": [
            {
                "name": "Cloud Practitioner",
                "issuer": "Example Cloud",
                "date": "2024-06-01",
            }
        ],
        "projects": [
            {
                "title": "Resume Builder",
                "description": "Created a multi-step resume builder with AI-assisted content.",
            }
        ],
        "languages": [{"language_name": "English", "proficiency": "Professional"}],
    }
