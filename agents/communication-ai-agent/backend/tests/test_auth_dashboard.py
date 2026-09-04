def test_guest_login_returns_token_and_dashboard_loads(client):
    guest_response = client.post("/api/auth/guest")

    assert guest_response.status_code == 200
    guest_payload = guest_response.get_json()
    assert guest_payload["token"]
    assert guest_payload["user"]["email"] == "guest@student.local"

    dashboard_response = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {guest_payload['token']}"},
    )

    assert dashboard_response.status_code == 200
    dashboard_payload = dashboard_response.get_json()
    assert "sessions_completed" in dashboard_payload
    assert "today_communication_challenge" in dashboard_payload


def test_guest_login_is_idempotent(client):
    first = client.post("/api/auth/guest")
    second = client.post("/api/auth/guest")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["user"]["id"] == second.get_json()["user"]["id"]
