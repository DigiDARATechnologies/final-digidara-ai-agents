"""The student never reads "you passed" on a capstone they have not passed."""
from app.api.routes import final_feedback

REVIEW = "You PASSED with a score of 80.0 / 100.\n\nYour project demonstrates a solid understanding of EDA."


def test_a_failed_viva_replaces_the_passed_sentence():
    text = final_feedback(REVIEW, True, False, 80)
    assert "PASSED" not in text
    assert "the viva was not passed" in text
    assert "solid understanding" in text


def test_a_passed_capstone_keeps_its_review():
    assert final_feedback(REVIEW, True, True, 80) == REVIEW


def test_a_failed_code_review_is_left_as_written():
    review = "You did not pass. Add tests."
    assert final_feedback(review, False, False, 40) == review
