"""Unit coverage for OpenAI web-search-backed interview question planning."""

import json
import os
import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from ai.question_generation import build_interview_questions, fetch_live_real_questions


class LiveRealQuestionTests(unittest.TestCase):
    def setUp(self):
        self.create = Mock()
        self.fake_client = SimpleNamespace(
            responses=SimpleNamespace(create=self.create)
        )

    def test_successful_search_returns_valid_questions(self):
        self.create.return_value = SimpleNamespace(output_text=json.dumps([
            {"question": "What is the difference between a JOIN and a UNION?"},
            {"question": "What is the difference between a JOIN and a UNION?"},
        ]))

        with patch("ai.question_generation.search_client", self.fake_client):
            questions = fetch_live_real_questions(
                "Data Analyst", "beginner", "technical", 2
            )

        self.assertEqual([item["source"] for item in questions], ["real"])
        self.assertEqual(len(questions), 1)
        options = self.create.call_args.kwargs
        self.assertEqual(options["model"], "gpt-5.5")
        self.assertEqual(options["timeout"], 45.0)
        self.assertEqual(options["max_output_tokens"], 8192)
        self.assertEqual(
            options["tools"][0]["filters"]["allowed_domains"],
            ["glassdoor.com", "geeksforgeeks.org"],
        )

    def test_malformed_output_falls_back_gracefully(self):
        self.create.return_value = SimpleNamespace(output_text="not JSON")
        with patch("ai.question_generation.search_client", self.fake_client):
            questions = fetch_live_real_questions(
                "Data Analyst", "beginner", "technical", 2
            )
        self.assertEqual(questions, [])

    def test_api_error_returns_empty_list_without_crashing(self):
        self.create.side_effect = RuntimeError("search unavailable")
        with patch("ai.question_generation.search_client", self.fake_client):
            questions = fetch_live_real_questions(
                "Data Analyst", "beginner", "technical", 2
            )
        self.assertEqual(questions, [])

    def test_search_failure_is_not_retried_with_another_model(self):
        self.create.side_effect = RuntimeError(
            "allowed_domains is not supported for this model"
        )
        with patch.dict(os.environ, {"OPENAI_SEARCH_MODEL": "custom-model"}), patch(
            "ai.question_generation.search_client", self.fake_client
        ):
            questions = fetch_live_real_questions(
                "Data Analyst", "beginner", "technical", 1
            )

        self.assertEqual(questions, [])
        self.assertEqual(self.create.call_count, 1)

    def test_timeout_fails_fast_without_sdk_or_application_retries(self):
        self.create.side_effect = TimeoutError("simulated slow web search")
        with (
            patch("ai.question_generation.search_client", self.fake_client),
            patch("ai.question_generation.time.perf_counter", side_effect=[100.0, 114.8]),
            self.assertLogs("ai.question_generation", level="ERROR") as logs,
        ):
            questions = fetch_live_real_questions(
                "Data Analyst", "beginner", "technical", 2
            )

        self.assertEqual(questions, [])
        self.assertEqual(self.create.call_count, 1)
        self.assertTrue(any("failed after 14.80s" in entry for entry in logs.output))

    def test_synchronous_plan_never_waits_for_web_search(self):
        with patch("ai.question_generation.fetch_live_real_questions") as search:
            plan = build_interview_questions(
                "Data Analyst", "beginner", "technical", 4,
                chat_fn=lambda *_args, **_kwargs: "[]",
                generate_ai_question=lambda asked, skill_area: {
                    "question": f"AI question {len(asked) + 1}?",
                    "topic_area": "data analysis",
                },
                rng=random.Random(1),
            )

        search.assert_not_called()
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(item["source"] == "ai_generated" for item in plan))

    def test_dedicated_search_client_disables_retries_and_uses_background_timeout(self):
        with (
            patch("ai.question_generation.OpenAI") as openai_client,
            patch.dict(os.environ, {"WEB_SEARCH_TIMEOUT_SECONDS": "45"}),
            patch("ai.question_generation.search_client", None),
        ):
            from ai.question_generation import _get_search_client
            _get_search_client()

        openai_client.assert_called_once_with(
            api_key=os.environ["OPENAI_API_KEY"], max_retries=0, timeout=45.0
        )

    def test_missing_real_questions_are_topped_up_with_ai(self):
        with patch("ai.question_generation.fetch_live_real_questions", return_value=[]):
            plan = build_interview_questions(
                "Data Analyst", "beginner", "technical", 4,
                chat_fn=lambda *_args, **_kwargs: "[]",
                generate_ai_question=lambda asked, skill_area: {
                    "question": f"AI question {len(asked) + 1}?", "topic_area": "testing",
                },
                rng=random.Random(1),
            )
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(item["source"] == "ai_generated" for item in plan))
