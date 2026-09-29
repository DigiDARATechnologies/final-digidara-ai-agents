"""The speaking_transcribe gateway action: phones record the spoken answer and
send it base64-encoded through the JSON gateway to be transcribed."""
import base64

import pytest

from app.routes import speaking


def invoke(client, action, payload):
    return client.post("/api/invoke", json={"action": action, "payload": payload})


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
