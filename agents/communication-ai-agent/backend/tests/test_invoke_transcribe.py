"""The speaking_transcribe gateway action: phones record the spoken answer and
send it base64-encoded through the JSON gateway to be transcribed."""
import base64

import pytest

from app.routes import speaking


def invoke(client, action, payload):
    return client.post("/api/invoke", json={"action": action, "payload": payload}, headers={"X-DigiDARA-User-Id": "user-1"})


@pytest.fixture()
def token(client):
    return invoke(client, "bridge_identity", {"name": "Learner", "email": "learner@example.test"}).get_json()["authToken"]


def test_recorded_audio_is_transcribed_through_the_gateway(client, token, monkeypatch):
    received = {}

    def fake_transcribe(audio_bytes, filename, content_type):
        received.update(audio=audio_bytes, filename=filename, content_type=content_type)
        return "I enjoy reading books"

    monkeypatch.setattr(speaking.groq_service, "transcribe_speaking_audio", fake_transcribe)
    audio = b"\x00\x01fake-mp4-audio"
    response = invoke(client, "speaking_transcribe", {
        "authToken": token, "audio_data": base64.b64encode(audio).decode(), "audio_type": "audio/mp4",
    })
    assert response.status_code == 200
    assert response.get_json()["transcript"] == "I enjoy reading books"
    assert received == {"audio": audio, "filename": "speaking-answer.m4a", "content_type": "audio/mp4"}


@pytest.mark.parametrize("payload,status,code", [
    ({"audio_data": "AAAA", "audio_type": "audio/webm"}, 401, "unauthenticated"),
    ({"audio_type": "audio/webm"}, 400, "AUDIO_MISSING"),
    ({"audio_data": "not base64!", "audio_type": "audio/webm"}, 400, "INVALID_AUDIO"),
    ({"audio_data": "AAAA", "audio_type": "video/avi"}, 400, "INVALID_AUDIO"),
])
def test_bad_transcribe_requests_are_rejected_with_a_reason(client, token, payload, status, code):
    if status != 401:
        payload = {**payload, "authToken": token}
    response = invoke(client, "speaking_transcribe", payload)
    assert response.status_code == status
    assert response.get_json()["error_code"] == code


def test_live_preview_is_transcribed_through_its_own_route(client, token, monkeypatch):
    monkeypatch.setattr(speaking.groq_service, "transcribe_speaking_audio", lambda audio, filename, content_type: "I went to")
    response = invoke(client, "speaking_transcribe_preview", {
        "authToken": token, "audio_data": base64.b64encode(b"partial").decode(), "audio_type": "audio/webm",
    })
    assert response.status_code == 200
    assert response.get_json()["transcript"] == "I went to"


def test_live_preview_allows_a_preview_every_three_seconds(client, token, monkeypatch):
    monkeypatch.setattr(speaking.groq_service, "transcribe_speaking_audio", lambda audio, filename, content_type: "text")
    payload = {"authToken": token, "audio_data": base64.b64encode(b"partial").decode(), "audio_type": "audio/webm"}
    statuses = [invoke(client, "speaking_transcribe_preview", payload).status_code for _ in range(20)]
    assert statuses == [200] * 20


def _provider_replies(monkeypatch, app, *replies):
    from unittest.mock import Mock

    from app.services import groq_speaking

    app.config["OPENAI_API_KEY"] = "sk-test"
    built = []
    for status, body in replies:
        request = groq_speaking.httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
        built.append(groq_speaking.httpx.Response(status, json=body, request=request))
    post = Mock(side_effect=built)
    monkeypatch.setattr(groq_speaking.httpx, "post", post)
    monkeypatch.setattr(groq_speaking.time, "sleep", lambda seconds: None)
    return post


def _preview(client, token):
    return invoke(client, "speaking_transcribe_preview", {
        "authToken": token, "audio_data": base64.b64encode(b"\x1a\x45audio").decode(), "audio_type": "audio/webm",
    })


def test_a_recording_the_provider_cannot_read_is_not_a_server_failure(client, app, token, monkeypatch):
    # OpenAI answers 400 to a very short or cut-off recording.
    post = _provider_replies(monkeypatch, app, (400, {"error": {"code": "invalid_value", "message": "corrupted"}}))
    response = _preview(client, token)
    assert response.status_code == 400 and post.call_count == 1
    assert "couldn't hear any words" in response.get_json()["message"]


def test_a_blip_at_the_provider_is_tried_once_more(client, app, token, monkeypatch):
    post = _provider_replies(monkeypatch, app, (429, {"error": {"code": "rate_limit_exceeded"}}), (200, {"text": "Hello there"}))
    response = _preview(client, token)
    assert response.status_code == 200 and response.get_json()["transcript"] == "Hello there"
    assert post.call_count == 2


def test_an_account_without_credits_is_an_error_with_its_cause_and_not_retried(client, app, token, monkeypatch, caplog):
    post = _provider_replies(monkeypatch, app, (429, {"error": {"code": "insufficient_quota"}}))
    response = _preview(client, token)
    assert response.status_code == 502 and post.call_count == 1
    assert "insufficient_quota" not in response.get_data(as_text=True)
    assert any(r.levelname == "ERROR" and "insufficient_quota" in r.getMessage() for r in caplog.records)


def test_the_days_first_two_requests_at_once_both_get_the_challenge(client, app, token, monkeypatch):
    from unittest.mock import Mock

    from sqlalchemy.exc import IntegrityError

    from app.routes import daily_challenges

    # The other request created today's rows first: this one hits the unique key once.
    today = Mock(side_effect=[IntegrityError("INSERT", {}, Exception("Duplicate entry")), {"all_completed": False, "activities": []}])
    monkeypatch.setattr(daily_challenges, "today_status", today)
    response = invoke(client, "daily_challenge_today", {"authToken": token})
    assert response.status_code == 200 and response.get_json()["all_completed"] is False
    assert today.call_count == 2


def test_a_daily_challenge_that_keeps_failing_is_a_clean_503(client, app, token, monkeypatch):
    from unittest.mock import Mock

    from sqlalchemy.exc import OperationalError

    from app.routes import daily_challenges

    monkeypatch.setattr(daily_challenges, "today_status", Mock(side_effect=OperationalError("SELECT", {}, Exception("gone away"))))
    response = invoke(client, "daily_challenge_today", {"authToken": token})
    assert response.status_code == 503
