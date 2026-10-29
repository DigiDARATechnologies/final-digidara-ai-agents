"""The writing chat never shows "null" or a field label the model copied."""
from app.services import groq_writing


def test_null_and_copied_labels_are_dropped(monkeypatch):
    monkeypatch.setattr(groq_writing, "_chat", lambda *args, **kwargs: (
        '{"reaction":"friendly acknowledgment","next_question":"What interests you most?","corrected_answer":"null"}'))
    result = groq_writing.generate_writing_chat_reply("life", "easy", [{"role": "user", "text": "I don't know"}])
    assert result["reply"] == "What interests you most?"
    assert result["reaction"] == "" and result["corrected_answer"] is None


def test_a_real_correction_is_kept(monkeypatch):
    monkeypatch.setattr(groq_writing, "_chat", lambda *args, **kwargs: (
        '{"reaction":"Nice idea!","next_question":"Why?","corrected_answer":"I like reading books."}'))
    result = groq_writing.generate_writing_chat_reply("hobbies", "easy", [{"role": "user", "text": "I likes read book"}])
    assert result["reply"] == "Nice idea! Why?" and result["corrected_answer"] == "I like reading books."
