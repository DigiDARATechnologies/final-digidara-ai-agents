from app.routes import writing
from app.models import WritingTurn
from app.services import groq_writing


def test_active_writing_session_returns_current_prompt(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        writing.groq_service,
        "generate_writing_prompt",
        lambda *args, **kwargs: "Write about one communication habit you want to improve.",
    )

    start_response = client.post(
        "/api/writing/start",
        json={
            "mode": "topic",
            "difficulty": "medium",
            "generated_topic_id": "writing-topic-1",
            "topic_title": "Communication Habits",
            "topic_description": "Write about communication habits and improvement.",
        },
        headers=auth_headers,
    )
    assert start_response.status_code == 201

    active_response = client.get("/api/writing/active", headers=auth_headers)
    assert active_response.status_code == 200
    active = active_response.get_json()["session"]
    assert active["session_id"] == start_response.get_json()["session_id"]
    assert active["turn_number"] == 1
    assert active["prompt"] == "Write about one communication habit you want to improve."
    assert active["status"] == "in_progress"


def test_writing_start_uses_fallback_prompt_when_ai_generation_fails(client, auth_headers, monkeypatch):
    monkeypatch.setattr(groq_writing, "_chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rate limited")))

    start_response = client.post(
        "/api/writing/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "writing-topic-fallback",
            "topic_title": "My Favourite Place",
            "topic_description": "Write simple sentences about a place you like to visit.",
        },
        headers=auth_headers,
    )

    assert start_response.status_code == 201
    data = start_response.get_json()
    assert data["prompt"] == "Write 5 to 8 simple sentences about My Favourite Place."
    assert data["turn_number"] == 1


def test_quick_check_uses_writing_service(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        writing.groq_service,
        "quick_grammar_check",
        lambda text: {"issues": [{"phrase": "She go", "suggestion": "She goes", "type": "grammar"}], "source": "test"},
    )

    response = client.post(
        "/api/writing/quick-check",
        json={"text": "She go to school every day."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["issues"][0]["suggestion"] == "She goes"


def test_live_check_fails_silently(client, auth_headers, monkeypatch):
    monkeypatch.setattr(writing.groq_service, "live_writing_insights", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rate limited")))

    response = client.post(
        "/api/writing/live-check",
        json={"text": "She go to school every day.", "difficulty": "easy", "mode": "topic"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "issues": [],
        "grade": None,
        "source": "fallback",
        "confidence": 0.0,
        "tone": "neutral",
        "is_duplicate": False,
    }


def test_live_writing_check_flags_obvious_errors_without_ai(monkeypatch):
    monkeypatch.setattr(groq_writing, "_chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rate limited")))

    cases = [
        ("i want to go to the temple.", "i", "I"),
        ("she go to school", "she go", "She goes"),
        ("I recieve messages", "recieve", "receive"),
    ]

    for text, expected_text, expected_suggestion in cases:
        result = groq_writing.live_writing_check(text, difficulty="easy", mode="topic", prompt="")
        assert result["issues"], text
        assert any(
            issue["text"] == expected_text and issue["suggestion"] == expected_suggestion
            for issue in result["issues"]
        )


def test_live_writing_check_accepts_flagged_spans_shape(monkeypatch):
    monkeypatch.setattr(
        groq_writing,
        "_chat",
        lambda *args, **kwargs: '{"flagged_spans":[{"start":0,"end":1,"text":"i","type":"grammar","explanation":"Capitalize I","suggestion":"I"}],"grade":8}',
    )

    result = groq_writing.live_writing_check("i agree today", difficulty="easy", mode="topic", prompt="")

    assert result["issues"][0]["text"] == "i"
    assert result["issues"][0]["suggestion"] == "I"


def test_writing_insights_returns_stored_weak_area_tags(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        writing.groq_service,
        "generate_writing_prompt",
        lambda *args, **kwargs: "Write about clear workplace communication.",
    )
    monkeypatch.setattr(
        writing.groq_service,
        "evaluate_writing_answer",
        lambda *args, **kwargs: {
            "corrected_answer": "She goes to meetings on time.",
            "better_natural_answer": "She always goes to meetings on time.",
            "short_feedback": "Check verb agreement.",
            "mistakes": [{"incorrect": "She go", "correct": "She goes", "type": "Subject Verb Agreement"}],
            "scores": {
                "grammar": 70,
                "vocabulary": 75,
                "clarity": 80,
                "spelling": 90,
                "relevance": None,
                "knowledge": 70,
                "overall": 75,
            },
        },
    )

    start_response = client.post(
        "/api/writing/start",
        json={
            "mode": "topic",
            "difficulty": "medium",
            "generated_topic_id": "writing-topic-2",
            "topic_title": "Communication Habits",
            "topic_description": "Write about communication habits and improvement.",
        },
        headers=auth_headers,
    )
    assert start_response.status_code == 201

    session_id = start_response.get_json()["session_id"]
    response = client.post(
        "/api/writing/respond",
        json={"session_id": session_id, "answer": "She go to meetings on time."},
        headers=auth_headers,
    )
    assert response.status_code == 200

    turn = WritingTurn.query.filter_by(session_id=session_id, turn_number=1).first()
    assert turn.weak_area_tags

    insights_response = client.get("/api/writing/insights", headers=auth_headers)
    assert insights_response.status_code == 200
    assert insights_response.get_json()["weak_areas"] == [{"tag": "subject-verb agreement", "count": 1}]
