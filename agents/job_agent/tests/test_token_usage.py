"""Unit tests for SaaS Token Economy & Dynamic Quota in DigiDARA Job Agent."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from job_agent.app import create_app
from job_agent.usage import (
    check_and_record_chat_usage,
    check_and_record_feed_usage,
    get_token_settings,
    get_user_daily_usage,
    update_token_settings,
)


class TokenUsageUnitTests(unittest.TestCase):
    def test_get_token_settings_fallback_defaults(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        settings = get_token_settings(cursor)
        self.assertEqual(settings["free_daily_feed_limit"], 20)
        self.assertEqual(settings["free_daily_chat_turns"], 10)
        self.assertEqual(settings["tokens_per_extra_feed"], 2000)
        self.assertEqual(settings["tokens_per_chat_turn"], 500)

    def test_get_token_settings_from_db_row(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "free_daily_feed_limit": 25,
            "free_daily_chat_turns": 15,
            "tokens_per_extra_feed": 3000,
            "tokens_per_chat_turn": 750,
        }
        settings = get_token_settings(cursor)
        self.assertEqual(settings["free_daily_feed_limit"], 25)
        self.assertEqual(settings["free_daily_chat_turns"], 15)
        self.assertEqual(settings["tokens_per_extra_feed"], 3000)
        self.assertEqual(settings["tokens_per_chat_turn"], 750)

    def test_update_token_settings(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "free_daily_feed_limit": 20,
            "free_daily_chat_turns": 10,
            "tokens_per_extra_feed": 2000,
            "tokens_per_chat_turn": 500,
        }
        res = update_token_settings(
            cursor,
            free_daily_feed_limit=30,
            tokens_per_extra_feed=2500,
        )
        self.assertEqual(res["free_daily_feed_limit"], 30)
        self.assertEqual(res["free_daily_chat_turns"], 10)
        self.assertEqual(res["tokens_per_extra_feed"], 2500)
        self.assertEqual(res["tokens_per_chat_turn"], 500)
        self.assertTrue(cursor.execute.called)

    def test_feed_usage_within_free_quota(self):
        cursor = MagicMock()
        # Row 1: settings
        # Row 2: daily usage
        cursor.fetchone.side_effect = [
            {"free_daily_feed_limit": 20, "free_daily_chat_turns": 10, "tokens_per_extra_feed": 2000, "tokens_per_chat_turn": 500},
            {"jobs_viewed": 5, "chat_turns": 2, "tokens_spent": 0},
        ]
        res = check_and_record_feed_usage(cursor, "user_1", requested_count=10)
        self.assertTrue(res["is_free"])
        self.assertEqual(res["tokens_charged"], 0)
        self.assertEqual(res["jobs_served"], 10)
        self.assertEqual(res["free_quota_remaining"], 5)
        self.assertEqual(res["total_viewed_today"], 15)
        self.assertFalse(res["insufficient_tokens"])

    def test_feed_usage_exceeding_free_quota_with_tokens(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"free_daily_feed_limit": 20, "free_daily_chat_turns": 10, "tokens_per_extra_feed": 2000, "tokens_per_chat_turn": 500},
            {"jobs_viewed": 20, "chat_turns": 2, "tokens_spent": 0},
        ]
        res = check_and_record_feed_usage(cursor, "user_1", requested_count=10, user_token_balance=50000)
        self.assertFalse(res["is_free"])
        self.assertEqual(res["tokens_charged"], 2000)
        self.assertEqual(res["jobs_served"], 10)
        self.assertEqual(res["free_quota_remaining"], 0)
        self.assertEqual(res["total_viewed_today"], 30)
        self.assertFalse(res["insufficient_tokens"])

    def test_feed_usage_exceeding_free_quota_insufficient_tokens(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"free_daily_feed_limit": 20, "free_daily_chat_turns": 10, "tokens_per_extra_feed": 2000, "tokens_per_chat_turn": 500},
            {"jobs_viewed": 20, "chat_turns": 2, "tokens_spent": 0},
        ]
        res = check_and_record_feed_usage(cursor, "user_1", requested_count=10, user_token_balance=500)
        self.assertFalse(res["is_free"])
        self.assertTrue(res["insufficient_tokens"])
        self.assertEqual(res["required_tokens"], 2000)
        self.assertEqual(res["current_balance"], 500)

    def test_chat_usage_free_turn(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"free_daily_feed_limit": 20, "free_daily_chat_turns": 10, "tokens_per_extra_feed": 2000, "tokens_per_chat_turn": 500},
            {"jobs_viewed": 5, "chat_turns": 4, "tokens_spent": 0},
        ]
        res = check_and_record_chat_usage(cursor, "user_1")
        self.assertTrue(res["is_free"])
        self.assertEqual(res["tokens_charged"], 0)
        self.assertEqual(res["free_turns_remaining"], 5)
        self.assertEqual(res["total_turns_today"], 5)
        self.assertFalse(res["insufficient_tokens"])

    def test_chat_usage_exhausted_quota_insufficient_tokens(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"free_daily_feed_limit": 20, "free_daily_chat_turns": 10, "tokens_per_extra_feed": 2000, "tokens_per_chat_turn": 500},
            {"jobs_viewed": 5, "chat_turns": 10, "tokens_spent": 0},
        ]
        res = check_and_record_chat_usage(cursor, "user_1", user_token_balance=100)
        self.assertFalse(res["is_free"])
        self.assertTrue(res["insufficient_tokens"])
        self.assertEqual(res["required_tokens"], 500)
        self.assertEqual(res["current_balance"], 100)


if __name__ == "__main__":
    unittest.main()
