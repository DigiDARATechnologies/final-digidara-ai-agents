import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

import routes.analytics as analytics


class AnalyticsRoutesTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_daily_fills_missing_dates_with_zero_usage(self):
        rows = [
            {
                "date": date(2026, 8, 8),
                "requests": 20,
                "prompt_tokens": 14343,
                "completion_tokens": 635,
                "total_tokens": 14978,
                "estimated_cost": Decimal("0.008963"),
            }
        ]

        with patch("routes.analytics.db.query", return_value=(rows, None)) as query:
            with self.app.test_request_context(
                "/api/analytics/daily?student_id=1&start_date=2026-08-07&end_date=2026-08-08"
            ):
                response = analytics.daily()

        payload = response.get_json()
        self.assertEqual(payload["range"], {"start_date": "2026-08-07", "end_date": "2026-08-08"})
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["date"], "2026-08-07")
        self.assertEqual(payload["items"][0]["requests"], 0)
        self.assertEqual(payload["items"][0]["total_tokens"], 0)
        self.assertEqual(payload["items"][0]["estimated_cost"], 0)
        self.assertEqual(payload["items"][1]["date"], "2026-08-08")
        self.assertEqual(payload["items"][1]["requests"], 20)
        self.assertEqual(payload["items"][1]["total_tokens"], 14978)
        self.assertAlmostEqual(payload["items"][1]["estimated_cost"], 0.008963)
        query.assert_called_once()

    def test_summary_applies_student_and_date_filters(self):
        summary_row = {
            "total_requests": 20,
            "prompt_tokens": 14343,
            "completion_tokens": 635,
            "total_tokens": 14978,
            "estimated_cost": Decimal("0.008963"),
            "interviews_with_usage": 2,
            "total_interviews": 2,
        }
        today_row = {
            "requests": 20,
            "tokens": 14978,
            "estimated_cost": Decimal("0.008963"),
            "interviews": 2,
        }

        with patch("routes.analytics.db.query", side_effect=[(summary_row, None), (today_row, None)]) as query:
            with self.app.test_request_context(
                "/api/analytics/summary?student_id=1&start_date=2026-08-08&end_date=2026-08-08"
            ):
                response = analytics.summary()

        payload = response.get_json()
        self.assertEqual(payload["range"], {"start_date": "2026-08-08", "end_date": "2026-08-08"})
        self.assertEqual(payload["summary"]["total_tokens"], 14978)
        self.assertAlmostEqual(payload["summary"]["estimated_cost"], 0.008963)
        self.assertEqual(payload["today"]["tokens"], 14978)
        self.assertEqual(payload["today"]["interviews"], 2)

        first_call_args = query.call_args_list[0].args
        self.assertEqual(first_call_args[1], (1, date(2026, 8, 8), date(2026, 8, 8), 1, date(2026, 8, 8), date(2026, 8, 8)))

        second_call_args = query.call_args_list[1].args
        self.assertEqual(second_call_args[1], (1,))


if __name__ == "__main__":
    unittest.main()
