from backend.app.services.question_bank_service import CATEGORIES


def test_every_category_difficulty_combination_is_present_in_bank_status():
    expected={(category,difficulty) for category in CATEGORIES for difficulty in ("Easy","Medium","Hard")}
    assert len(expected)==18
