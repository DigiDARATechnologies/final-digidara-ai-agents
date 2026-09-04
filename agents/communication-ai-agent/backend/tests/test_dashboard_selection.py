from app.routes.dashboard import _module_selection, _valid_score


def modules(*items):
    return [
        {"key": key, "label": key.title(), "average": average, "completed": completed}
        for key, average, completed in items
    ]


def test_dashboard_selection_picks_highest_and_lowest():
    result = _module_selection(modules(
        ("speaking", 8.5, 2),
        ("writing", 6.5, 2),
        ("pronunciation", 7.5, 2),
    ))
    assert result["best"]["key"] == "speaking"
    assert result["needs_work"]["key"] == "writing"


def test_dashboard_selection_handles_one_module_and_no_data():
    one = _module_selection(modules(("pronunciation", 7.9, 1)))
    assert one["best"]["key"] == "pronunciation"
    assert one["needs_work"]["status"] == "insufficient_data"

    empty = _module_selection(modules(("speaking", None, 0), ("writing", None, 0)))
    assert empty["best"]["status"] == "no_data"
    assert empty["needs_work"]["status"] == "no_data"


def test_dashboard_selection_handles_tied_modules():
    result = _module_selection(modules(("speaking", 7.9, 1), ("writing", 7.9, 1)))
    assert result["best"]["status"] == "tied"
    assert result["needs_work"]["status"] == "tied"
    assert result["best"]["key"] is None


def test_dashboard_score_validation_rejects_invalid_values_and_normalizes_percent():
    assert _valid_score(79) == 7.9
    assert _valid_score(7.9) == 7.9
    assert _valid_score(None) is None
    assert _valid_score(-1) is None
    assert _valid_score(101) is None
    assert _valid_score("not-a-score") is None
