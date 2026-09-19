"""Regression coverage for cross-interview question and topic rotation."""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

with patch("openai.OpenAI", return_value=object()):
    import groq_client
    from ai.question_generation import _prioritized_topic_areas
    from services import interview_state


def payload(topic_area, question):
    return json.dumps({"topic_area": topic_area, "question": question})


class HistoryContextTests(unittest.TestCase):
    def test_question_history_is_main_only_ordered_and_bounded(self):
        with patch.object(
            interview_state.db,
            "query",
            return_value=([{"question": "Previous?"}], 0),
        ) as query:
            result = interview_state.recent_questions_for_student(
                1, "technical", "Python", "beginner"
            )

        sql = " ".join(query.call_args.args[0].split())
        self.assertEqual(result, ["Previous?"])
        self.assertIn("d.is_followup = FALSE", sql)
        self.assertIn("ORDER BY d.created_at DESC, d.id DESC", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(query.call_args.args[1], (1, "technical", "Python", "beginner", 40))

    def test_custom_topic_history_matches_canonical_text_across_difficulties(self):
        with patch.object(
            interview_state.db,
            "query",
            return_value=([{"topic_area": "reconciliation loop"}], 0),
        ) as query:
            result = interview_state.recent_topic_areas_for_student(
                1, "technical", "  KUBERNETES   Operators  "
            )

        sql = " ".join(query.call_args.args[0].split())
        self.assertEqual(result, ["reconciliation loop"])
        self.assertIn("REGEXP_REPLACE", sql)
        self.assertIn("d.is_followup = FALSE", sql)
        self.assertIn("d.topic_area IS NOT NULL", sql)
        self.assertNotIn("i.difficulty", sql)
        self.assertEqual(
            query.call_args.args[1],
            (1, "technical", "kubernetes operators", 80),
        )

    def test_hr_topic_history_uses_null_subject(self):
        with patch.object(interview_state.db, "query", return_value=([], 0)) as query:
            interview_state.recent_topic_areas_for_student(1, "hr", None)
        sql = " ".join(query.call_args.args[0].split())
        self.assertIn("i.subject IS NULL", sql)
        self.assertEqual(query.call_args.args[1], (1, "hr", 80))

    def test_question_context_keeps_current_first_and_normalizes_duplicates(self):
        merged = interview_state.merge_question_context(
            ["  What is a LIST?  ", "Current second?"],
            ["what is a list", "Historical third!"],
        )
        self.assertEqual(
            merged,
            ["What is a LIST?", "Current second?", "Historical third!"],
        )

    def test_topic_context_normalizes_and_deduplicates(self):
        merged = interview_state.merge_topic_area_context(
            ["  Teamwork  ", "Conflict Resolution"],
            ["teamwork", "  Career   Goals "],
        )
        self.assertEqual(merged, ["teamwork", "conflict resolution", "career goals"])


class TopicRotationTests(unittest.TestCase):
    def test_checklist_prioritizes_unseen_then_least_recently_used(self):
        candidates = ["a", "b", "c", "d"]
        # History is newest-first: b is newer than a, while c/d are unseen.
        self.assertEqual(
            _prioritized_topic_areas(candidates, ["b", "a"]),
            ["c", "d", "a", "b"],
        )

    def test_preset_rejects_wrong_topic_and_regenerates_for_selected_area(self):
        role_skills = groq_client.PRESET_ROLE_SKILLS["python fullstack developer"]["beginner"]
        recent = list(role_skills[:2])
        selected = role_skills[2]
        with patch.object(
            groq_client,
            "_chat",
            side_effect=[
                payload("exceptions", "What is exception handling?"),
                payload(selected, "What is a Python module used for?"),
            ],
        ) as chat:
            result = groq_client.generate_question(
                "technical", "Python Fullstack Developer", "beginner", [], recent,
                role_skills=role_skills,
            )

        self.assertEqual(result["topic_area"], selected.casefold())
        self.assertEqual(chat.call_count, 2)
        retry_prompt = chat.call_args_list[1].args[0][0]["content"]
        self.assertIn("previous JSON response was rejected", retry_prompt)

    def test_custom_topic_rejects_normalized_excluded_area(self):
        with patch.object(
            groq_client,
            "_chat",
            side_effect=[
                payload("  RECONCILIATION   LOOP ", "What is a reconciliation loop?"),
                payload("leader election", "Why is leader election useful?"),
            ],
        ) as chat:
            result = groq_client.generate_question(
                "technical",
                "Kubernetes Operators",
                "intermediate",
                [],
                ["reconciliation loop"],
            )

        self.assertEqual(result["topic_area"], "leader election")
        self.assertEqual(chat.call_count, 2)

    def test_hr_rejects_wrong_area_and_regenerates_for_checklist_selection(self):
        selected = groq_client.HR_QUESTION_AREAS["intermediate"][2]
        recent = groq_client.HR_QUESTION_AREAS["intermediate"][:2]
        with patch.object(
            groq_client,
            "_chat",
            side_effect=[
                payload("teamwork and collaboration", "How do you help a team?"),
                payload(selected, "How do you prioritize competing deadlines?"),
            ],
        ) as chat:
            result = groq_client.generate_question(
                "hr", None, "intermediate", [], recent
            )

        self.assertEqual(result["topic_area"], selected)
        self.assertEqual(chat.call_count, 2)

    def test_custom_fallback_also_avoids_recent_area(self):
        recent = ["fundamentals", "core concepts"]
        with (
            patch.object(groq_client, "_chat", return_value="not json") as chat,
            self.assertLogs("llm_client", level="ERROR"),
        ):
            result = groq_client.generate_question(
                "technical", "Kubernetes Operators", "beginner", [], recent
            )

        self.assertEqual(chat.call_count, 3)
        self.assertEqual(result["topic_area"], "practical usage")
        self.assertNotIn(result["topic_area"], recent)

    def test_malformed_and_overlong_topic_areas_are_rejected(self):
        with self.assertRaises(ValueError):
            groq_client._question_payload("not json")
        with self.assertRaisesRegex(ValueError, "concise label"):
            groq_client._question_payload(payload(
                "one two three four five six seven eight nine",
                "What does this do?",
            ))


if __name__ == "__main__":
    unittest.main()
