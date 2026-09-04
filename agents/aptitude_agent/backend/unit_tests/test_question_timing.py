import pytest

from backend.app.services.question_timing import question_time_seconds


@pytest.mark.parametrize(
    ("difficulty","expected"),
    [
        ("Easy",60),("Beginner",60),
        ("Medium",90),("Intermediate",90),
        ("Hard",120),("Advanced",120),
    ],
)
def test_question_time_supports_both_difficulty_naming_schemes(difficulty,expected):
    assert question_time_seconds(difficulty,{})==expected


def test_question_time_uses_configured_tier_values():
    config={"QUESTION_SECONDS_EASY":45,"QUESTION_SECONDS_MEDIUM":75,"QUESTION_SECONDS_HARD":105}
    assert question_time_seconds("Easy",config)==45
    assert question_time_seconds("Intermediate",config)==75
    assert question_time_seconds("Hard",config)==105


def test_question_time_rejects_unknown_difficulty():
    with pytest.raises(ValueError,match="Unsupported question difficulty"):
        question_time_seconds("Expert",{})
