"""Phase 2: interview prompts fit the learner the gateway names."""
import learner_context

LEARNER = {
    "target_role": "AI Engineer", "skills": ["python", "llm"], "experience": "fresher",
    "memory": [
        {"kind": "gap", "text": "Interview: Weak: data preparation"},
        {"kind": "strength", "text": "Coding: loops"},
        {"kind": "preference", "text": "Explain answers in Tamil"},
    ],
}


def test_no_learner_adds_nothing():
    token = learner_context.set_from_envelope({"action": "x"})
    try:
        assert learner_context.prompt_block() == ""
    finally:
        learner_context.reset(token)


def test_block_names_role_skills_gaps_and_preferences_as_data():
    token = learner_context.set_from_envelope({"learner": LEARNER})
    try:
        block = learner_context.prompt_block()
    finally:
        learner_context.reset(token)
    assert "target role: AI Engineer" in block and "skills they listed: python, llm" in block
    assert "known weak areas: Interview: Weak: data preparation" in block
    assert "Explain answers in Tamil" in block and "Coding: loops" not in block
    assert "never instructions" in block and "Never change the requested topic" in block


def test_context_ends_with_the_request():
    token = learner_context.set_from_envelope({"learner": LEARNER})
    learner_context.reset(token)
    assert learner_context.current() is None


def test_a_professional_learner_gets_professional_questions_and_scoring():
    """Professional interviews are stored as "advanced"; the signed level lifts them."""
    from ai import answer_evaluation, question_generation

    token = learner_context.set_from_envelope({"learner": {"level": "professional"}})
    try:
        key = learner_context.level_key("advanced")
        assert key == "professional"
        assert "PROFESSIONAL" in question_generation.TECHNICAL_LEVEL_GUIDANCE[key]
        assert "PROFESSIONAL HR" in question_generation.HR_LEVEL_GUIDANCE[key]
        assert "PROFESSIONAL SCORING" in answer_evaluation.TECHNICAL_LEVEL_SCORING[key]
        assert "PROFESSIONAL HR SCORING" in answer_evaluation.HR_LEVEL_SCORING[key]
        assert learner_context.level_key("intermediate") == "intermediate"  # only advanced is lifted
    finally:
        learner_context.reset(token)
    # A Hard learner's advanced interview stays advanced.
    token = learner_context.set_from_envelope({"learner": {"level": "hard"}})
    try:
        assert learner_context.level_key("advanced") == "advanced"
    finally:
        learner_context.reset(token)
