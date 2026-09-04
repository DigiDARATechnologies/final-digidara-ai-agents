import io


def invoke(client, action, payload=None):
    return client.post("/api/invoke", json={"action": action, "payload": payload or {}})


def test_health_and_missing_action(client):
    response = invoke(client, "health")
    assert response.status_code == 200
    assert response.get_json()["agent_name"] == "resume_builder_agent"
    assert client.post("/api/invoke", json={"payload": {}}).status_code == 400


def test_profile_and_existing_resume_route_are_reentered(client):
    profile = invoke(client, "ensure_profile", {"user_id": "digidara:test@example.com", "name": "Test User", "email": "test@example.com"})
    assert profile.status_code == 200
    created = invoke(client, "create_resume", {"user_id": "digidara:test@example.com", "title": "Integration resume"})
    assert created.status_code == 201
    resume = created.get_json()["data"]
    fetched = invoke(client, "get_resume", {"user_id": "digidara:test@example.com", "resume_id": resume["id"]})
    assert fetched.status_code == 200
    assert fetched.get_json()["data"]["title"] == "Integration resume"


def test_unknown_action_and_pdf_headers_are_preserved(client):
    # A small valid canonical document keeps this adapter test focused on
    # binary response preservation rather than individual template fields.
    created = invoke(client, "create_resume", {
        "user_id": "test-user",
        "title": "PDF integration resume",
        "summary": "Software engineer building reliable web applications.",
        "personal_info": {"name": "Test User", "email": "test@example.com"},
        "skills": [{"skill_name": "Python"}, {"skill_name": "React"}],
    })
    resume_id = created.get_json()["data"]["id"]
    assert invoke(client, "not-real", {}).status_code == 404
    pdf = invoke(client, "export_pdf", {"user_id": "test-user", "resume_id": resume_id})
    assert pdf.status_code == 200
    assert pdf.content_type == "application/pdf"
    assert "attachment" in pdf.headers["Content-Disposition"]
    assert pdf.data.startswith(b"%PDF")


def test_multipart_import_reaches_existing_route(client):
    response = client.post(
        "/api/invoke",
        data={
            "action": "analyze_upload",
            "payload": '{"user_id":"test-user"}',
            "file": (io.BytesIO(
                b"Jane Doe\njane@example.com\n\nSummary\nSoftware engineer building web applications.\n\nSkills\nPython, React\n\nExperience\nSoftware Engineer at Example Co\nBuilt reliable product features."
            ), "resume.txt", "text/plain"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["file"]["name"] == "resume.txt"
