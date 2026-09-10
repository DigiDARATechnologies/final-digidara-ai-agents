import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from job_agent import automation
from job_agent.app import create_app


class AutomationScheduleTests(unittest.TestCase):
    @patch("job_agent.automation._record_outcome")
    @patch("job_agent.automation.queue_greenhouse_collection")
    @patch("job_agent.automation._claim_today", return_value=True)
    def test_due_schedule_queues_greenhouse_once(self, claim, queue, record):
        queue.return_value = {"ready": True, "source_count": 2, "queued_count": 2, "already_queued_count": 0}
        result = automation.queue_due_automation(datetime(2026, 9, 9, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")))
        self.assertTrue(result["due"])
        queue.assert_called_once_with(admin_id=None)
        record.assert_called_once_with(queued_count=2)

    @patch("job_agent.automation._claim_today")
    def test_before_schedule_does_not_claim_or_queue(self, claim):
        result = automation.queue_due_automation(datetime(2026, 9, 9, 8, 59, tzinfo=ZoneInfo("Asia/Kolkata")))
        self.assertFalse(result["due"])
        self.assertEqual(result["reason"], "not_due")
        claim.assert_not_called()


class AutomationRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(testing=True).test_client()
        self.headers = {"X-Digidara-User-Id": "admin", "X-Digidara-Is-Admin": "true"}

    @patch("job_agent.routes.get_automation_settings")
    def test_get_automation_is_admin_only(self, get_settings):
        get_settings.return_value = {"enabled": False, "schedule_time": "09:00", "timezone": "Asia/Kolkata"}
        response = self.client.post("/api/invoke", json={"action": "admin_get_automation", "payload": {}}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["automation"]["enabled"])

    @patch("job_agent.routes.set_automation_enabled")
    def test_toggle_automation(self, set_enabled):
        set_enabled.return_value = {"enabled": True, "schedule_time": "09:00", "timezone": "Asia/Kolkata"}
        response = self.client.post("/api/invoke", json={"action": "admin_update_automation", "payload": {"enabled": True}}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        set_enabled.assert_called_once_with(True)

    @patch("job_agent.routes.get_db")
    def test_saved_jobs_are_available_outside_the_current_feed(self, get_db):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchall.return_value = [{
            "id": 7,
            "title": "Junior Developer",
            "company": "Example Co",
            "apply_url": "https://example.test/job/7",
            "status": "active",
        }]
        get_db.return_value = db

        response = self.client.post(
            "/api/invoke",
            json={"action": "get_saved_jobs", "payload": {}},
            headers={"X-Digidara-User-Id": "learner"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["jobs"][0]["id"], 7)


if __name__ == "__main__":
    unittest.main()
