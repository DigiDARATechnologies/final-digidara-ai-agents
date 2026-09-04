from app import create_app
from app.extensions import db
import pytest


def create_resume(client, payload):
    response = client.post("/api/resume", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def test_create_app_requires_secret_key_without_explicit_insecure_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr("app.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "staging")

    class MissingSecretConfig:
        TESTING = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'missing-secret.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    try:
        create_app(MissingSecretConfig)
    except RuntimeError as exc:
        assert "SECRET_KEY must be configured" in str(exc)
    else:
        raise AssertionError("create_app accepted the insecure default SECRET_KEY without opt-in")


def test_create_app_allows_insecure_default_in_testing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    class InsecureDevConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'insecure-dev.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    insecure_app = create_app(InsecureDevConfig)

    assert insecure_app.config["SECRET_KEY"] == "dev-secret-key"
    with insecure_app.app_context():
        db.engine.dispose()


def test_create_app_rejects_dev_user_header_in_production(tmp_path, monkeypatch):
    monkeypatch.setattr("app.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("FLASK_ENV", "production")

    class ProductionHeaderConfig:
        TESTING = True
        SECRET_KEY = "production-test-secret"
        ALLOW_DEV_USER_HEADER = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'production-header.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    with pytest.raises(RuntimeError, match="ALLOW_DEV_USER_HEADER"):
        create_app(ProductionHeaderConfig)


def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


def test_cors_allows_required_development_origins(client):
    response = client.options(
        "/api/resumes",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-User-Id",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5173"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]


def test_secure_browser_session_owns_resume_without_user_id(client):
    session_response = client.get("/api/session")
    assert session_response.status_code == 200
    session_data = session_response.get_json()["data"]
    assert session_data["userId"].startswith("guest_")
    assert session_data["csrfToken"]

    create_response = client.post(
        "/api/resume",
        headers={"X-CSRF-Token": session_data["csrfToken"]},
        json={"title": "Secure Session Resume"},
    )
    assert create_response.status_code == 201
    created = create_response.get_json()["data"]
    assert created["user_id"] == session_data["userId"]

    list_response = client.get("/api/resumes")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.get_json()["data"]] == [created["id"]]


def test_non_testing_cookie_session_requires_csrf(tmp_path):
    class SecurityConfig:
        TESTING = False
        SECRET_KEY = "non-testing-csrf-secret-key"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'security.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    security_app = create_app(SecurityConfig)
    with security_app.app_context():
        db.create_all()
        security_client = security_app.test_client()
        session_data = security_client.get("/api/session").get_json()["data"]

        blocked = security_client.post("/api/resume", json={"title": "Blocked"})
        assert blocked.status_code == 403

        allowed = security_client.post(
            "/api/resume",
            headers={"X-CSRF-Token": session_data["csrfToken"]},
            json={"title": "Protected"},
        )
        assert allowed.status_code == 201
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_x_user_id_header_ignored_when_not_explicitly_allowed_outside_test_mode(tmp_path):
    class HeaderDisabledConfig:
        TESTING = False
        SECRET_KEY = "non-testing-header-secret-key"
        ALLOW_DEV_USER_HEADER = False
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'header-disabled.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    secure_app = create_app(HeaderDisabledConfig)
    with secure_app.app_context():
        db.create_all()
        secure_client = secure_app.test_client()

        response = secure_client.post(
            "/api/resume",
            headers={"X-User-Id": "header-user"},
            json={"title": "Header Should Not Authenticate"},
        )

        assert response.status_code == 403
        assert "secure session" in response.get_json()["message"]
        assert secure_client.get("/api/resumes", headers={"X-User-Id": "header-user"}).status_code == 400
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_non_testing_rate_limiter_blocks_repeated_expensive_requests(tmp_path):
    class RateLimitConfig:
        TESTING = False
        SECRET_KEY = "non-testing-rate-limit-secret-key"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'rate-limit.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    rate_app = create_app(RateLimitConfig)
    with rate_app.app_context():
        db.create_all()
        rate_client = rate_app.test_client()
        session_data = rate_client.get("/api/session").get_json()["data"]
        headers = {"X-CSRF-Token": session_data["csrfToken"]}

        for _index in range(20):
            response = rate_client.post(
                "/api/ai/generate-bullets",
                headers=headers,
                json={"raw_input": "too short", "role": "Analyst", "industry": "Tech"},
            )
            assert response.status_code == 400

        blocked = rate_client.post(
            "/api/ai/generate-bullets",
            headers=headers,
            json={"raw_input": "too short", "role": "Analyst", "industry": "Tech"},
        )

        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_non_testing_rate_limiter_blocks_resume_creation_spam(tmp_path):
    class CreateRateLimitConfig:
        TESTING = False
        SECRET_KEY = "non-testing-create-rate-limit-secret-key"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'create-rate-limit.db').as_posix()}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    rate_app = create_app(CreateRateLimitConfig)
    with rate_app.app_context():
        db.create_all()
        rate_client = rate_app.test_client()
        session_data = rate_client.get("/api/session").get_json()["data"]
        headers = {"X-CSRF-Token": session_data["csrfToken"]}

        for index in range(30):
            response = rate_client.post("/api/resume", headers=headers, json={"title": f"Resume {index}"})
            assert response.status_code == 201

        blocked = rate_client.post("/api/resume", headers=headers, json={"title": "Blocked"})
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_templates_endpoint(client):
    response = client.get("/api/templates")

    assert response.status_code == 200
    template_ids = {template["id"] for template in response.get_json()["data"]}
    from app.template_catalog import TEMPLATE_CATALOG

    assert template_ids == {template_id for template_id, *_rest in TEMPLATE_CATALOG}

    detail_response = client.get("/api/templates/steady-form")
    assert detail_response.status_code == 200
    assert detail_response.get_json()["data"]["category"] == "ATS"


def test_database_error_payload_includes_real_cause():
    from sqlalchemy.exc import OperationalError

    from app.errors import database_error_payload

    error = OperationalError(
        "SELECT 1",
        {},
        Exception("Access denied for user 'root'@'localhost' (using password: YES)"),
    )

    payload = database_error_payload(error)

    assert payload["success"] is False
    assert payload["error"] == "database authentication failed"
    assert "Access denied" in payload["detail"]


def test_create_fetch_update_and_delete_resume(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)
    resume_id = created["id"]

    fetch_response = client.get(
        f"/api/resume/{resume_id}", headers={"X-User-Id": "test-user"}
    )
    assert fetch_response.status_code == 200
    fetched = fetch_response.get_json()["data"]
    assert fetched["title"] == "Software Engineer Resume"
    assert fetched["personal_info"]["email"] == "demo@example.com"
    assert fetched["education"][0]["start_date"] == "2020"
    assert fetched["education"][0]["end_date"] == "2024"
    assert fetched["education"][0]["cgpa"] == "8.7"
    assert fetched["experience"][0]["ai_generated_bullets"]

    update_response = client.put(
        f"/api/resume/{resume_id}",
        headers={"X-User-Id": "test-user"},
        json={
            "title": "Updated Resume",
            "template_choice": "classic",
            "summary": "Updated professional summary.",
            "skills": [{"skill_name": "Flask"}, {"skill_name": "MySQL"}],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()["data"]
    assert updated["title"] == "Updated Resume"
    assert updated["template_choice"] == "classic-serif"
    assert updated["summary"] == "Updated professional summary."
    assert [skill["skill_name"] for skill in updated["skills"]] == ["Flask", "MySQL"]

    list_response = client.get("/api/resumes?user_id=test-user")
    assert list_response.status_code == 200
    assert len(list_response.get_json()["data"]) == 1

    delete_response = client.delete(
        f"/api/resume/{resume_id}", headers={"X-User-Id": "test-user"}
    )
    assert delete_response.status_code == 200

    missing_response = client.get(
        f"/api/resume/{resume_id}", headers={"X-User-Id": "test-user"}
    )
    assert missing_response.status_code == 404


def test_saved_resume_ats_analysis_is_persisted(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)
    response = client.post(
        f"/api/resumes/{created['id']}/ats",
        headers={"X-User-Id": "test-user"},
        json={"job_description": "Python React Flask SQL dashboards automation"},
    )

    assert response.status_code == 200
    analysis = response.get_json()["data"]
    assert 0 <= analysis["score"]["normalized_score"] <= 100
    assert analysis["categories"]
    assert analysis["jobMatch"]["keywordsEvaluated"] > 0

    refreshed = client.get(
        f"/api/resume/{created['id']}", headers={"X-User-Id": "test-user"}
    ).get_json()["data"]
    assert refreshed["ats_score"] == analysis["score"]["normalized_score"]
    assert refreshed["last_analyzed_at"]


def test_project_ai_generated_bullets_are_persisted(client, sample_resume_payload):
    sample_resume_payload["projects"][0]["ai_generated_bullets"] = [
        "Built an AI-assisted resume builder with practical workflows."
    ]
    created = create_resume(client, sample_resume_payload)

    fetched = client.get(
        f"/api/resume/{created['id']}", headers={"X-User-Id": "test-user"}
    ).get_json()["data"]

    assert fetched["projects"][0]["ai_generated_bullets"] == [
        "Built an AI-assisted resume builder with practical workflows."
    ]


def test_saved_resume_ats_uses_target_role_when_no_job_description_is_given(client, sample_resume_payload):
    sample_resume_payload["target_role"] = "AI Engineer"
    created = create_resume(client, sample_resume_payload)

    response = client.post(
        f"/api/resumes/{created['id']}/ats",
        headers={"X-User-Id": "test-user"},
        json={},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["analysis_type"] == "job_match"


def test_plural_resume_contract_aliases(client, sample_resume_payload):
    create_response = client.post("/api/resumes", json=sample_resume_payload)
    assert create_response.status_code == 201
    created = create_response.get_json()["data"]

    fetch_response = client.get(f"/api/resumes/{created['id']}?user_id=test-user")
    assert fetch_response.status_code == 200
    assert fetch_response.get_json()["data"]["title"] == sample_resume_payload["title"]

    patch_response = client.patch(
        f"/api/resumes/{created['id']}",
        json={"user_id": "test-user", "title": "Plural Route Resume"},
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["data"]["title"] == "Plural Route Resume"

    delete_response = client.delete(f"/api/resumes/{created['id']}?user_id=test-user")
    assert delete_response.status_code == 200


def test_archive_and_restore_resume(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)

    archive_response = client.post(
        f"/api/resumes/{created['id']}/archive",
        json={"user_id": "test-user"},
    )
    assert archive_response.status_code == 200
    assert archive_response.get_json()["data"]["status"] == "archived"

    restore_response = client.post(
        f"/api/resumes/{created['id']}/restore",
        json={"user_id": "test-user"},
    )
    assert restore_response.status_code == 200
    assert restore_response.get_json()["data"]["status"] == "draft"


def test_complete_resume_is_returned_by_completed_filter(client, sample_resume_payload):
    payload = {
        **sample_resume_payload,
        "target_role": "Software Engineer",
        "publications": [
            {
                "title": "Resume Automation Notes",
                "description": "Published notes on resume automation workflows.",
                "date": "2024-07-01",
            }
        ],
    }
    created = create_resume(client, payload)

    assert created["completion_percentage"] == 100
    assert created["status"] == "completed"

    completed_response = client.get("/api/resumes?user_id=test-user&status=completed")
    draft_response = client.get("/api/resumes?user_id=test-user&status=draft")

    assert completed_response.status_code == 200
    assert [item["id"] for item in completed_response.get_json()["data"]] == [created["id"]]
    assert draft_response.status_code == 200
    assert draft_response.get_json()["data"] == []


def test_legacy_full_draft_is_treated_as_completed_in_dashboard_filter(client, sample_resume_payload):
    payload = {
        **sample_resume_payload,
        "target_role": "Software Engineer",
        "status": "draft",
        "publications": [
            {
                "title": "Resume Automation Notes",
                "description": "Published notes on resume automation workflows.",
                "date": "2024-07-01",
            }
        ],
    }
    created = create_resume(client, payload)

    with client.application.app_context():
        from app.models import Resume

        resume = db.session.get(Resume, created["id"])
        resume.status = "draft"
        db.session.commit()

    response = client.get("/api/resumes?user_id=test-user&status=completed")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == created["id"]
    assert data[0]["status"] == "completed"


def test_update_reuses_existing_personal_info(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)
    original_personal_info_id = created["personal_info"]["id"]

    update_response = client.put(
        f"/api/resume/{created['id']}",
        json={
            "user_id": sample_resume_payload["user_id"],
            "personal_info": {
                "name": "Demo User",
                "email": "new@example.com",
                "phone": "555-0199",
                "location": "Hybrid",
                "links": ["https://portfolio.example.com"],
            },
        },
    )

    assert update_response.status_code == 200
    personal_info = update_response.get_json()["data"]["personal_info"]
    assert personal_info["id"] == original_personal_info_id
    assert personal_info["email"] == "new@example.com"
    assert personal_info["phone"] == "555-0199"
    assert personal_info["location"] == "Hybrid"
    assert personal_info["links"] == ["https://portfolio.example.com"]


def test_experience_accepts_month_year_dates(client, sample_resume_payload):
    sample_resume_payload["experience"][0]["start_date"] = "January 2024"
    sample_resume_payload["experience"][0]["end_date"] = "June 2024"

    created = create_resume(client, sample_resume_payload)

    assert created["experience"][0]["start_date"] == "January 2024"
    assert created["experience"][0]["end_date"] == "June 2024"


def test_create_resume_defaults_missing_title(client):
    response = client.post("/api/resume", json={"user_id": "test-user"})
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["title"] == "Untitled Resume"
    assert data["user_id"] == "test-user"


def test_create_and_update_resume_persists_experience_level(client):
    response = client.post(
        "/api/resume",
        json={"user_id": "test-user", "title": "Graduate Resume", "experience_level": "fresher"},
    )

    assert response.status_code == 201
    created = response.get_json()["data"]
    assert created["experience_level"] == "fresher"

    updated = client.put(
        f"/api/resume/{created['id']}",
        json={"user_id": "test-user", "experience_level": "experienced"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["experience_level"] == "experienced"


def test_create_resume_requires_user_id(client):
    response = client.post("/api/resume", json={"title": "Missing User"})
    assert response.status_code == 400
    assert "user_id" in response.get_json()["message"]


def test_create_resume_auto_creates_missing_user(client):
    response = client.post(
        "/api/resume",
        json={"user_id": "new-user", "title": "Untitled Resume"},
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["id"]
    assert data["user_id"] == "new-user"


def test_list_resumes_requires_user_id(client):
    response = client.get("/api/resumes")
    assert response.status_code == 400
    assert "user_id" in response.get_json()["message"]


def test_update_and_delete_unknown_resume_return_404(client):
    update_response = client.put("/api/resume/999", json={"title": "Missing"})
    assert update_response.status_code == 404

    delete_response = client.delete("/api/resume/999")
    assert delete_response.status_code == 404


def test_create_blank_draft_ignores_empty_nested_rows(client):
    response = client.post(
        "/api/resume",
        json={
            "user_id": "test-user",
            "title": "Untitled Resume",
            "template_choice": "modern",
            "personal_info": {"name": "", "email": "", "links": []},
            "education": [{"school": "", "degree": ""}],
            "skills": [{"skill_name": ""}],
        },
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["personal_info"] is None
    assert data["education"] == []
    assert data["skills"] == []


def test_invalid_template_is_rejected(client, sample_resume_payload):
    sample_resume_payload["template_choice"] = "unsafe-template"
    response = client.post("/api/resume", json=sample_resume_payload)

    assert response.status_code == 400
    assert "template_choice" in response.get_json()["message"]


def test_update_cannot_change_resume_owner(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)

    response = client.put(
        f"/api/resume/{created['id']}",
        json={"user_id": "other-user", "title": "Hijacked Resume"},
    )

    assert response.status_code == 404

    fetch_response = client.get(f"/api/resume/{created['id']}?user_id=test-user")
    assert fetch_response.status_code == 200
    assert fetch_response.get_json()["data"]["user_id"] == "test-user"
    assert fetch_response.get_json()["data"]["title"] == "Software Engineer Resume"


def test_user_context_blocks_cross_user_resume_access(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)

    fetch_response = client.get(
        f"/api/resume/{created['id']}",
        headers={"X-User-Id": "other-user"},
    )
    update_response = client.put(
        f"/api/resume/{created['id']}",
        headers={"X-User-Id": "other-user"},
        json={"title": "Other User Edit"},
    )
    delete_response = client.delete(
        f"/api/resume/{created['id']}",
        headers={"X-User-Id": "other-user"},
    )

    assert fetch_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404


def test_missing_user_context_cannot_read_existing_resume(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)

    response = client.get(f"/api/resume/{created['id']}")

    assert response.status_code == 404


def test_duplicate_resume_requires_matching_user_context(client, sample_resume_payload):
    created = create_resume(client, sample_resume_payload)

    blocked_response = client.post(
        f"/api/resume/{created['id']}/duplicate",
        headers={"X-User-Id": "other-user"},
        json={"title": "Blocked Copy"},
    )
    assert blocked_response.status_code == 404

    duplicate_response = client.post(
        f"/api/resume/{created['id']}/duplicate",
        headers={"X-User-Id": "test-user"},
        json={"title": "Resume Copy"},
    )
    assert duplicate_response.status_code == 201
    duplicate = duplicate_response.get_json()["data"]
    assert duplicate["id"] != created["id"]
    assert duplicate["user_id"] == "test-user"
    assert duplicate["title"] == "Resume Copy"
    assert duplicate["skills"][0]["skill_name"] == "Python"


def test_canonical_target_role_accepted(client, sample_resume_payload):
    sample_resume_payload["target_role"] = "DATA ANALYST"
    created = create_resume(client, sample_resume_payload)
    assert created["target_role"] == "DATA ANALYST"


def test_legacy_role_aliases_accepted(client, sample_resume_payload):
    payload = {**sample_resume_payload}
    payload.pop("target_role", None)
    payload["targetRole"] = "SENIOR DATA ANALYST"
    created = create_resume(client, payload)
    assert created["target_role"] == "SENIOR DATA ANALYST"


def test_empty_legacy_alias_does_not_overwrite_populated_target_role(client, sample_resume_payload):
    sample_resume_payload["target_role"] = "DATA ANALYST"
    created = create_resume(client, sample_resume_payload)

    # Partial update with empty legacy alias 'role': ''
    update_res = client.put(
        f"/api/resume/{created['id']}",
        json={"role": "", "user_id": "test-user"},
        headers={"X-User-Id": "test-user"},
    )
    assert update_res.status_code == 200
    updated = update_res.get_json()["data"]
    assert updated["target_role"] == "DATA ANALYST"
