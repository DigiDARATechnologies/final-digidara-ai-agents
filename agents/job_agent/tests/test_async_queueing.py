import unittest
from unittest.mock import MagicMock, patch

from job_agent import service
from job_agent.app import create_app
from job_agent.providers import sync


class QueueSourceRunOnceTests(unittest.TestCase):
    def _database(self, fetch_results):
        db = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetch_results
        db.cursor.return_value = cursor
        return db, cursor

    @patch("job_agent.service.get_db")
    def test_returns_existing_active_run_without_inserting(self, get_db):
        db, cursor = self._database([{"id": 7}, {"id": 91}])
        get_db.return_value = db

        run_id, created = service.queue_source_run_once(7, "admin")

        self.assertEqual((run_id, created), (91, False))
        self.assertFalse(any("INSERT INTO job_ingestion_runs" in call.args[0] for call in cursor.execute.call_args_list))
        db.commit.assert_called_once()

    @patch("job_agent.service.get_db")
    def test_inserts_when_source_has_no_active_run(self, get_db):
        db, cursor = self._database([{"id": 7}, None])
        cursor.lastrowid = 92
        get_db.return_value = db

        run_id, created = service.queue_source_run_once(7, "admin")

        self.assertEqual((run_id, created), (92, True))
        self.assertTrue(any("INSERT INTO job_ingestion_runs" in call.args[0] for call in cursor.execute.call_args_list))


class ProviderBatchQueueTests(unittest.TestCase):
    @patch("job_agent.providers.sync.process_run")
    @patch("job_agent.providers.sync.queue_source_run_once", side_effect=[(101, True), (102, False)])
    @patch("job_agent.providers.sync._active_greenhouse_sources")
    @patch("job_agent.providers.sync.sync_greenhouse_sources")
    def test_greenhouse_only_queues_and_never_fetches_in_request(
        self, sync_sources, active_sources, queue_once, process_run
    ):
        active_sources.return_value = [
            {"id": 1, "name": "greenhouse:first"},
            {"id": 2, "name": "greenhouse:second"},
        ]

        result = sync.queue_greenhouse_collection("admin")

        sync_sources.assert_called_once_with()
        self.assertEqual(result["queued_count"], 1)
        self.assertEqual(result["already_queued_count"], 1)
        self.assertEqual(result["queued"][0]["run_id"], 101)
        process_run.assert_not_called()

    @patch("job_agent.providers.sync.get_apify_status", return_value={"ready": False, "reason": "not configured"})
    @patch("job_agent.providers.sync.sync_apify_sources")
    def test_apify_not_ready_does_not_touch_sources(self, sync_sources, _status):
        result = sync.queue_apify_collection("admin", "linkedin")

        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "not configured")
        sync_sources.assert_not_called()

    @patch("job_agent.providers.sync.queue_source_run_once", return_value=(201, True))
    @patch("job_agent.providers.sync._active_apify_sources")
    @patch("job_agent.providers.sync.sync_apify_sources")
    @patch("job_agent.providers.sync.get_apify_status", return_value={"ready": True, "reason": ""})
    def test_apify_platform_queues_only_requested_actor(
        self, _status, _sync_sources, active_sources, queue_once
    ):
        active_sources.return_value = [
            {"id": 3, "name": "apify:a", "parser_config": '{"platform":"linkedin"}'},
            {"id": 4, "name": "apify:b", "parser_config": '{"platform":"naukri"}'},
        ]

        result = sync.queue_apify_collection("admin", "naukri")

        self.assertTrue(result["ready"])
        self.assertEqual(result["source_count"], 1)
        queue_once.assert_called_once_with(4, "admin")


class AsyncAdminRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(testing=True).test_client()
        self.headers = {"X-Digidara-User-Id": "admin", "X-Digidara-Is-Admin": "true"}
        self.queued = {
            "ready": True,
            "source_count": 1,
            "queued_count": 1,
            "already_queued_count": 0,
            "queued": [{"source_id": 1, "source_name": "greenhouse:test", "run_id": 10}],
            "already_queued": [],
        }

    @patch("job_agent.routes.queue_greenhouse_collection")
    def test_gateway_action_returns_202_without_waiting_for_collection(self, queue_collection):
        queue_collection.return_value = self.queued

        response = self.client.post(
            "/api/invoke",
            json={"action": "admin_greenhouse_run", "payload": {}},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["queued_count"], 1)
        queue_collection.assert_called_once_with(admin_id="admin")

    @patch("job_agent.routes.queue_apify_collection")
    def test_apify_action_preserves_manual_platform_filter(self, queue_collection):
        queue_collection.return_value = self.queued

        response = self.client.post(
            "/api/invoke",
            json={"action": "admin_apify_run", "payload": {"platform": "naukri"}},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 202)
        queue_collection.assert_called_once_with(admin_id="admin", platform="naukri")

    def test_non_admin_cannot_queue_collection(self):
        response = self.client.post(
            "/api/invoke",
            json={"action": "admin_greenhouse_run", "payload": {}},
            headers={"X-Digidara-User-Id": "learner", "X-Digidara-Is-Admin": "false"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
