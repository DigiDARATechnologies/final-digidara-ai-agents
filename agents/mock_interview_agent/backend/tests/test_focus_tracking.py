import unittest
from unittest.mock import patch

from app import create_app
from services.focus_tracking import finalize_open_focus_events, focus_summary


class FocusTrackingRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    @patch("routes.interviews.focus_summary")
    @patch("routes.interviews.db.query")
    def test_opens_active_interview_event_idempotently(self, query, summary):
        event_uuid = "00000000-0000-4000-8000-000000000001"
        query.side_effect = [
            (None, 1),
            ({"returned_at": None, "away_seconds": None}, 0),
        ]
        summary.return_value = {
            "focus_loss_count": 1,
            "focus_loss_total_seconds": 0,
            "integrity_flagged": False,
        }

        response = self.client.post(
            "/api/interviews/7/focus-events",
            json={"event_uuid": event_uuid, "action": "left", "source": "visibility"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["event_open"])
        self.assertEqual(response.get_json()["focus_loss_count"], 1)
        self.assertIn("INSERT IGNORE INTO interview_focus_events", query.call_args_list[0].args[0])

    @patch("routes.interviews.db.query")
    def test_rejects_event_for_inactive_interview(self, query):
        query.side_effect = [
            (None, 0),
            (None, 0),
            ({"status": "completed"}, 0),
        ]

        response = self.client.post(
            "/api/interviews/7/focus-events",
            json={
                "event_uuid": "00000000-0000-4000-8000-000000000002",
                "action": "left",
                "source": "window_blur",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("active interview", response.get_json()["error"])

    def test_rejects_invalid_event_identifier(self):
        response = self.client.post(
            "/api/interviews/7/focus-events",
            json={"event_uuid": "not-a-uuid", "action": "left"},
        )
        self.assertEqual(response.status_code, 400)


class FocusTrackingServiceTests(unittest.TestCase):
    @patch("services.focus_tracking.db.query")
    def test_summary_applies_event_and_duration_thresholds(self, query):
        query.return_value = (
            {"focus_loss_count": 3, "focus_loss_total_seconds": 60},
            0,
        )
        summary = focus_summary(9)
        self.assertEqual(summary["focus_loss_count"], 3)
        self.assertTrue(summary["integrity_flagged"])

    @patch("services.focus_tracking.focus_summary")
    @patch("services.focus_tracking.db.query")
    def test_finalization_closes_open_events_before_summarizing(self, query, summary):
        summary.return_value = {
            "focus_loss_count": 1,
            "focus_loss_total_seconds": 12,
            "integrity_flagged": False,
        }
        result = finalize_open_focus_events(9)
        self.assertIn("returned_at = NOW(6)", query.call_args.args[0])
        summary.assert_called_once_with(9)
        self.assertEqual(result["focus_loss_total_seconds"], 12)


if __name__ == "__main__":
    unittest.main()
