"""Job collection never leaves the Adzuna / JSearch free plans."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from job_agent import free_plan
from job_agent.providers import jsearch
from job_agent.providers.sync import todays_slice, upcoming_plan


def fake_db(counts):
    """A database whose COUNT(*) answers come from `counts` (seconds -> used)."""
    cursor = MagicMock()
    inserted = []

    def execute(sql, params):
        if sql.startswith("SELECT COUNT"):
            cursor.fetchone.return_value = (counts(params[1]),)
        elif sql.startswith("INSERT"):
            inserted.append(params[0])

    cursor.execute.side_effect = execute
    db = MagicMock()
    db.cursor.return_value = cursor
    return db, inserted


def test_a_call_inside_every_window_is_recorded_then_made():
    db, inserted = fake_db(lambda seconds: 10)
    with patch("job_agent.free_plan.get_db", return_value=db):
        free_plan.reserve_call("adzuna")
    assert inserted == ["adzuna"]


@pytest.mark.parametrize("provider,window_seconds,limit", [
    ("adzuna", 86400, 250), ("adzuna", 7 * 86400, 1000), ("adzuna", 31 * 86400, 2500), ("jsearch", 31 * 86400, 200)])
def test_a_full_day_week_or_month_refuses_without_calling(provider, window_seconds, limit):
    db, inserted = fake_db(lambda seconds: limit if seconds == window_seconds else 0)
    with patch("job_agent.free_plan.get_db", return_value=db), pytest.raises(free_plan.FreePlanLimitReached) as refused:
        free_plan.reserve_call(provider)
    assert inserted == [] and str(limit) in str(refused.value)


def test_a_full_minute_is_waited_out_not_refused():
    state = {"checks": 0}

    def counts(seconds):
        if seconds == 60:
            state["checks"] += 1
            return 25 if state["checks"] == 1 else 3
        return 0

    db, inserted = fake_db(counts)
    sleep = MagicMock()
    with patch("job_agent.free_plan.get_db", return_value=db):
        free_plan.reserve_call("adzuna", sleep=sleep)
    sleep.assert_called_once_with(5)
    assert inserted == ["adzuna"]


def test_jsearchs_fallback_request_counts_as_a_second_call():
    session = MagicMock()
    session.get.side_effect = [MagicMock(status_code=404), MagicMock(status_code=200, json=MagicMock(return_value={"data": []}))]
    calls = []
    with patch("job_agent.providers.jsearch._token", return_value="key"):
        jsearch.fetch_and_normalize("Java Developer fresher in Tamil Nadu", session=session, before_request=lambda: calls.append(1))
    assert len(calls) == 2


def test_a_refused_call_never_reaches_the_api():
    session = MagicMock()

    def refuse():
        raise free_plan.FreePlanLimitReached("full")

    with patch("job_agent.providers.jsearch._token", return_value="key"), pytest.raises(free_plan.FreePlanLimitReached):
        jsearch.fetch_and_normalize("x", session=session, before_request=refuse)
    session.get.assert_not_called()


def test_the_month_plan_fits_the_free_limits_and_mixes_roles_and_cities():
    plan = upcoming_plan(31, date(2026, 10, 1))
    adzuna_month = sum(len(city["roles"]) for day in plan for city in day["adzuna"])
    jsearch_month = sum(len(day["jsearch"]) for day in plan)
    assert adzuna_month <= 2500 and jsearch_month <= 200
    assert max(sum(len(c["roles"]) for c in day["adzuna"]) for day in plan) <= 250
    first, second = plan[0], plan[1]
    assert len(first["adzuna"]) == 7  # every city, every day
    for city in first["adzuna"]:
        assert len(set(city["roles"])) == len(city["roles"])
    # Neighbouring cities search different roles on the same day, and each day moves on.
    assert first["adzuna"][0]["roles"] != first["adzuna"][1]["roles"]
    assert first["adzuna"][0]["roles"] != second["adzuna"][0]["roles"]
    assert set(first["jsearch"]).isdisjoint(second["jsearch"])


def test_every_role_reaches_every_city_within_days():
    seen = set()
    for day in upcoming_plan(4, date(2026, 10, 1)):
        seen.update((role, city["city"]) for city in day["adzuna"] for role in city["roles"])
    assert len(seen) == 224


def test_a_short_quota_day_runs_fewer_without_shifting_the_rotation():
    full = todays_slice(list(range(224)), 70, date(2026, 10, 5))
    short = todays_slice(list(range(224)), 70, date(2026, 10, 5), take=20)
    assert short == full[:20]
    assert todays_slice(list(range(224)), 70, date(2026, 10, 5), take=0) == []
