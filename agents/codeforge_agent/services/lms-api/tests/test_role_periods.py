"""Role periods: only activity inside the current target role's periods counts."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.role_periods import clean_periods, in_periods  # noqa: E402


class RolePeriodsTest(unittest.TestCase):
    def test_no_periods_counts_everything(self):
        self.assertIsNone(clean_periods(None))
        self.assertIsNone(clean_periods([]))
        self.assertTrue(in_periods(datetime(2020, 1, 1), None))

    def test_only_activity_inside_a_period_counts(self):
        periods = clean_periods([
            {"start": None, "end": "2026-10-01T00:00:00"},
            {"start": "2026-10-10T00:00:00", "end": None},
        ])
        self.assertTrue(in_periods(datetime(2026, 9, 30), periods))
        self.assertFalse(in_periods(datetime(2026, 10, 5), periods))
        self.assertTrue(in_periods("2026-10-11T08:00:00Z", periods))
        self.assertFalse(in_periods(None, periods))


if __name__ == "__main__":
    unittest.main()
