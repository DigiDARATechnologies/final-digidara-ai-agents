"""Pronunciation practice never gives a learner the same word or sentence twice,
and spreads items across learners."""
from app.routes import pronunciation as routes
from app.services import groq_pronunciation
from app.services.groq_common import FALLBACK_PRONUNCIATION_ITEMS


def item(text, item_type="word"):
    return {"text": text, "item_type": item_type, "difficulty": "medium", "source": "groq", "metadata": {}}


def scripted(monkeypatch, texts):
    """The AI answers with these texts in turn; records what it was asked."""
    calls = []
    queue = list(texts)

    def generate(practice_mode, difficulty, recent_items=None, variety_hint=None):
        calls.append({"recent": list(recent_items or []), "hint": variety_hint})
        return item(queue.pop(0) if queue else "Communication", "word" if practice_mode == "word" else "sentence")

    monkeypatch.setattr(routes.groq_service, "generate_pronunciation_item", generate)
    return calls


def generate(client, headers, mode="word", difficulty="medium"):
    response = client.post("/api/pronunciation/generate", json={"practice_mode": mode, "difficulty": difficulty}, headers=headers)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]["text"]


def test_a_word_the_learner_already_had_is_never_given_again(client, auth_headers, monkeypatch):
    # The AI keeps proposing "Communication"; the learner gets it once only.
    scripted(monkeypatch, ["Communication", "communication.", "COMMUNICATION", "Negotiate"])
    assert generate(client, auth_headers) == "Communication"
    assert generate(client, auth_headers) == "Negotiate"


def test_a_repeat_at_another_difficulty_still_counts_as_a_repeat(client, auth_headers, monkeypatch):
    scripted(monkeypatch, ["Schedule", "Schedule", "Deadline"])
    assert generate(client, auth_headers, difficulty="easy") == "Schedule"
    assert generate(client, auth_headers, difficulty="hard") == "Deadline"


def test_each_request_asks_for_variety_and_lists_what_to_avoid(client, auth_headers, monkeypatch):
    calls = scripted(monkeypatch, ["Garden", "Market"])
    generate(client, auth_headers)
    generate(client, auth_headers)
    assert all(call["hint"] and "letter" in call["hint"] for call in calls)
    assert "Garden" in calls[1]["recent"]


def test_when_the_ai_only_repeats_an_unused_built_in_word_is_given(client, auth_headers, monkeypatch):
    scripted(monkeypatch, ["Teacher"] * 20)
    first = generate(client, auth_headers, difficulty="easy")
    second = generate(client, auth_headers, difficulty="easy")
    assert first == "Teacher" and second != "Teacher"
    easy_words = {entry[0] for entry in FALLBACK_PRONUNCIATION_ITEMS[("word", "easy")]}
    assert second in easy_words


def test_sentences_never_repeat_either(client, auth_headers, monkeypatch):
    scripted(monkeypatch, ["I enjoy learning English.", "I enjoy learning English!", "We play cricket on Sundays."])
    assert generate(client, auth_headers, mode="sentence") == "I enjoy learning English."
    assert generate(client, auth_headers, mode="sentence") == "We play cricket on Sundays."


def test_a_word_another_learner_just_got_is_avoided_when_possible(client, monkeypatch):
    other = {"Authorization": f"Bearer {client.post('/api/auth/guest').get_json()['token']}"}
    mine = {"Authorization": f"Bearer {client.post('/api/auth/guest').get_json()['token']}"}
    scripted(monkeypatch, ["Strategy", "Strategy", "Feedback"])
    assert generate(client, other) == "Strategy"
    calls = scripted(monkeypatch, ["Strategy", "Feedback"])
    assert generate(client, mine) == "Feedback"
    assert "Strategy" in calls[0]["recent"]


def test_twelve_sessions_of_words_are_all_different(client, auth_headers, monkeypatch):
    # Even when the AI is down, the built-in bank alone gives 18 different words per level.
    monkeypatch.setattr(groq_pronunciation, "_chat", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("AI down")))
    given = [generate(client, auth_headers) for _ in range(12)]
    assert len(set(word.lower() for word in given)) == 12


def test_the_uniqueness_key_ignores_case_and_punctuation():
    assert routes._uniqueness_key("  Communication! ") == routes._uniqueness_key("communication")
    assert routes._uniqueness_key("I enjoy learning English.") == routes._uniqueness_key("i enjoy  learning english")
