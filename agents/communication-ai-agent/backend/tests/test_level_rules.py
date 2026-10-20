from app.services import learner_context, level_rules


def _as(level):
    return learner_context.set_from_envelope({"learner": {"level": level}})


def test_each_level_is_scored_more_strictly_than_the_one_below():
    token = _as("hard")
    try:
        assert "EASY" in level_rules.scoring_rule("easy") and "at most" not in level_rules.scoring_rule("easy")
        assert "MEDIUM" in level_rules.scoring_rule("medium")
        assert "HARD" in level_rules.scoring_rule("hard")
        assert level_rules.generation_rule("hard") == ""  # Hard keeps the prompt's own Hard style
    finally:
        learner_context.reset(token)


def test_a_professional_learner_gets_professional_questions_and_scoring_on_hard():
    token = _as("professional")
    try:
        assert level_rules.level_key("hard") == "professional"
        assert "PROFESSIONAL" in level_rules.scoring_rule("hard") and "workplace" in level_rules.generation_rule("hard")
        assert level_rules.level_key("medium") == "medium"  # only Hard is lifted
    finally:
        learner_context.reset(token)


def test_without_a_learner_hard_stays_hard():
    assert level_rules.level_key("hard") == "hard"
