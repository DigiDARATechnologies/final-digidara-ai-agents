from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.orchestrator import role_profiles
from app.orchestrator.routes import router


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('learner')}"}


def test_role_profile_is_generated_and_validated(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(
        role_profiles,
        "call_text",
        lambda *_args, **_kwargs: '''```json
        {"summary":"Builds accessible web interfaces.","skills":["React","TypeScript","Accessibility"],"declaration":{"capabilities":["Draft components","Review UI code","Suggest tests"],"limitations":["Needs authorization to deploy","Needs human review for security changes","Cannot access private systems"],"required_inputs":["Requirements","Existing code","Design constraints"],"suggested_next_actions":["Define scope","Create components","Run tests"]}}
        ```''',
    )
    with TestClient(app) as client:
        response = client.post(
            "/role-profiles/generate",
            json={"target_role": "Frontend Developer", "context": "React application"},
            headers=_headers(),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["target_role"] == "Frontend Developer"
    assert body["skills"] == ["React", "TypeScript", "Accessibility"]
    assert body["declaration"]["limitations"][0] == "Needs authorization to deploy"


def test_role_profile_rejects_unstructured_model_output(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(role_profiles, "call_text", lambda *_args, **_kwargs: "not JSON")
    with TestClient(app) as client:
        response = client.post(
            "/role-profiles/generate",
            json={"target_role": "Data Analyst"},
            headers=_headers(),
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "The model returned an invalid role profile."


def test_role_profile_requires_login():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post("/role-profiles/generate", json={"target_role": "Data Analyst"})
    assert response.status_code == 401
