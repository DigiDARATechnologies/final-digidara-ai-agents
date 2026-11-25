"""One mock interview never asks the same question twice, even reworded."""

import json
import random
import unittest
from unittest.mock import patch

from ai.question_generation import build_interview_questions
from ai.validators import _safe_fallback_question
from services import background_question_search as background
from services.question_history import is_repeated_question, questions_are_similar

from test_background_question_search import _Connection, _Cursor


def _no_shuffle():
    return type("NoShuffle", (), {"shuffle": staticmethod(lambda _items: None)})()


class SimilarityTests(unittest.TestCase):
    def test_reworded_questions_count_as_repeats(self):
        for first, second in (
            ("What is a Python list?", "what is a python list ?"),
            ("What is a list in Python?", "What's a Python list?"),
            ("Explain the purpose of a SQL JOIN?", "What is the purpose of a SQL JOIN?"),
            ("How do you handle conflict in a team?", "How do you handle conflict within your team?"),
        ):
            with self.subTest(first=first):
                self.assertTrue(questions_are_similar(first, second))

    def test_different_questions_are_not_repeats(self):
        for first, second in (
            ("What does git commit do?", "What does git push do?"),
            ("What is a Python variable?", "What does a Python function do?"),
            ("What is a primary key in SQL?", "What is the purpose of a SQL JOIN?"),
        ):
            with self.subTest(first=first):
                self.assertFalse(questions_are_similar(first, second))

    def test_is_repeated_question_checks_every_asked_question(self):
        asked = ["What is a Python variable?", "What is a Python list?"]
        self.assertTrue(is_repeated_question("What's a list in Python?", asked))
        self.assertFalse(is_repeated_question("What is a Python dictionary?", asked))


class PlanTests(unittest.TestCase):
    def test_duplicate_batch_items_are_replaced_by_spares(self):
        chat = lambda *_a, **_k: json.dumps({"questions": [
            {"topic_area": "a", "question": "What is a Python list?"},
            {"topic_area": "a", "question": "What's a list in Python?"},
            {"topic_area": "a", "question": "What is a Python list?"},
            {"topic_area": "a", "question": "What is a Python tuple?"},
            {"topic_area": "a", "question": "What is a Python set?"},
        ]})
        plan = build_interview_questions(
            "Python", "beginner", "technical", 3,
            chat_fn=chat, generate_ai_question=None, rng=_no_shuffle(),
            role_skills=["A"],
        )
        questions = [item["question"] for item in plan]
        self.assertEqual(questions, [
            "What is a Python list?", "What is a Python tuple?", "What is a Python set?",
        ])

    def test_batch_prompt_asks_for_spares_and_no_repeats(self):
        prompts = []

        def chat(messages, **_kwargs):
            prompts.append(messages[0]["content"])
            return '{"questions":[]}'

        build_interview_questions(
            "Python", "beginner", "technical", 5,
            chat_fn=chat, generate_ai_question=None, rng=_no_shuffle(),
            role_skills=["A"],
        )
        self.assertIn("add 5 spare items", prompts[0])
        self.assertIn("never ask the same question twice", prompts[0])

    def test_failed_ai_plans_never_repeat_for_any_length(self):
        for round_type, skills in (("hr", None), ("technical", ["Python", "SQL"])):
            for level in ("beginner", "intermediate", "advanced", "professional"):
                for count in (5, 10, 15):
                    with self.subTest(round=round_type, level=level, count=count):
                        plan = build_interview_questions(
                            "HR interview" if round_type == "hr" else "Developer",
                            level, round_type, count,
                            chat_fn=lambda *_a, **_k: '{"questions":[]}',
                            generate_ai_question=None, rng=random.Random(3),
                            role_skills=skills,
                        )
                        questions = [item["question"] for item in plan]
                        self.assertEqual(len(questions), count)
                        for index, question in enumerate(questions):
                            self.assertFalse(
                                is_repeated_question(question, questions[:index]),
                                question,
                            )

    def test_hr_fallback_has_enough_questions_for_the_longest_interview(self):
        for level in ("beginner", "intermediate", "advanced", "professional"):
            asked = []
            for _ in range(15):
                asked.append(_safe_fallback_question("HR interview", level, asked, round_type="hr"))
            self.assertEqual(len(set(asked)), 15, level)


class BackgroundSwapTests(unittest.TestCase):
    def test_real_question_that_repeats_the_interview_is_skipped(self):
        rows = [
            {"id": 10, "question_order": 1, "question": "What is a Python list?"},
            {"id": 11, "question_order": 2, "question": "What is a Python tuple?"},
            {"id": 12, "question_order": 3, "question": "What is a Python set?"},
        ]
        cursor = _Cursor(pending=rows)
        conn = _Connection(cursor)
        real = [
            {"question": "What's a list in Python?"},  # repeats the current question
            {"question": "What is a Python dictionary?"},
            {"question": "What is a Python dictionary?"},  # repeats the swap above
        ]
        with patch.object(background.db, "get_conn", return_value=conn):
            result = background.upgrade_unserved_questions_with_real(5, real)

        updates = [params for sql, params in cursor.executed if sql.lstrip().startswith("UPDATE")]
        self.assertEqual(result["upgraded"], 1)
        self.assertEqual(updates[0][0], "What is a Python dictionary?")


if __name__ == "__main__":
    unittest.main()
