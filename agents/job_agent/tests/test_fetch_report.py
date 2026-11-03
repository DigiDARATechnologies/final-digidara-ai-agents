"""The daily job fetching numbers Boss reports."""
from datetime import date, datetime

from job_agent import fetch_report


class Cursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(params)

    def fetchone(self):
        return {"runs": 2, "failed": 1, "fetched": 50, "inserted": 10, "updated": 40, "rejected": 0}

    def close(self):
        pass


class Db:
    def __init__(self):
        self.made = Cursor()

    def cursor(self, dictionary=False):
        return self.made

    def close(self):
        pass


def test_a_day_runs_midnight_to_midnight_in_india():
    cursor = Cursor()
    fetch_report.day_totals(cursor, date(2026, 11, 3))
    assert cursor.calls[0] == (datetime(2026, 11, 2, 18, 30), datetime(2026, 11, 3, 18, 30))


def test_it_prints_yesterday_and_today(monkeypatch, capsys):
    monkeypatch.setattr(fetch_report, "get_db", Db)
    fetch_report.main(datetime(2026, 11, 3, 20, 0))  # Already the 4th in India.
    assert capsys.readouterr().out.splitlines() == [
        "@jobs 2026-11-03 2 1 50 10 40 0",
        "@jobs 2026-11-04 2 1 50 10 40 0",
    ]
