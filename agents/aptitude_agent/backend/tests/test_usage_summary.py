def _usage(client, payload):
    return client.post("/api/invoke", json={"action": "usage_summary", "payload": payload})


def test_usage_is_zero_for_a_learner_without_an_aptitude_session(client):
    # A brand-new user has never opened the Aptitude Trainer: zero usage, not "Not reachable".
    for payload in ({}, {"sessionToken": ""}, {"sessionToken": "expired-or-garbage"}):
        response = _usage(client, payload)
        assert response.status_code == 200
        body = response.get_json()
        assert (body["agent_name"], body["total_tokens"], body["total_requests"]) == ("aptitude_agent", 0, 0)


def test_usage_reports_the_session_learner(client, auth_headers):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    response = _usage(client, {"sessionToken": token})
    assert response.status_code == 200
    assert response.get_json()["total_tokens"] == 0
