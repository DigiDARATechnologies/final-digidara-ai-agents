"""Display metadata must not alter the stored question text."""

import unittest

from services.interview_state import format_question_for_display


class QuestionDisplayTests(unittest.TestCase):
    def test_real_question_is_marked_without_changing_text(self):
        raw_question = "How would you optimize a slow SQL query?"
        payload = format_question_for_display({
            "question": raw_question,
            "source": "real",
        })

        self.assertEqual(payload["question"], raw_question)
        self.assertTrue(payload["is_frequently_asked"])

    def test_ai_generated_question_is_not_marked(self):
        payload = format_question_for_display({
            "question": "What is an index in a database?",
            "source": "ai_generated",
        })

        self.assertFalse(payload["is_frequently_asked"])


if __name__ == "__main__":
    unittest.main()
