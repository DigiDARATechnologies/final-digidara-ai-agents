"""Tests for automated active approval and 30-day retention pruning in DigiDARA Job Agent."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from job_agent.service import prune_expired_jobs, prune_expired_jobs_in_session


class PruneAndApprovalUnitTests(unittest.TestCase):
    def test_prune_expired_jobs_in_session_executes_update_and_delete(self):
        cursor = MagicMock()
        cursor.rowcount = 5

        outcome = prune_expired_jobs_in_session(cursor, max_age_days=30)
        self.assertEqual(outcome["expired_count"], 5)
        self.assertEqual(outcome["deleted_count"], 5)
        self.assertEqual(cursor.execute.call_count, 2)

        # Check that 30 days is passed to SQL queries
        call_args_list = cursor.execute.call_args_list
        # Query 1: UPDATE jobs SET status='expired'
        self.assertIn("UPDATE jobs", call_args_list[0][0][0])
        self.assertEqual(call_args_list[0][0][1], (30, 30))
        # Query 2: DELETE FROM jobs
        self.assertIn("DELETE FROM jobs", call_args_list[1][0][0])
        self.assertEqual(call_args_list[1][0][1], (30, 30))

    @patch("job_agent.service.get_db")
    def test_prune_expired_jobs_commits_and_returns_success(self, mock_get_db):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_get_db.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        res = prune_expired_jobs(max_age_days=30)
        self.assertTrue(res["success"])
        self.assertEqual(res["expired_count"], 3)
        self.assertEqual(res["deleted_count"], 3)
        self.assertTrue(mock_db.commit.called)
        self.assertTrue(mock_cursor.close.called)
        self.assertTrue(mock_db.close.called)


if __name__ == "__main__":
    unittest.main()
