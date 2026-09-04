import unittest
from unittest.mock import patch, MagicMock

from cert_app.agents.question_agent import (
    _web_search_question_count,
    _build_web_search_prompt,
    _call_web_search_llm,
    generate_questions,
)


class TestQuestionAgentWebSearch(unittest.TestCase):
    def test_beginner_difficulty_skips_web_search(self):
        """Beginner difficulty should return 0 web search questions."""
        count_beginner = _web_search_question_count(30, difficulty="beginner")
        self.assertEqual(count_beginner, 0)

        count_mixed = _web_search_question_count(30, difficulty="mixed")
        self.assertGreater(count_mixed, 0)
        self.assertLessEqual(count_mixed, 8)

        count_intermediate = _web_search_question_count(30, difficulty="intermediate")
        self.assertGreater(count_intermediate, 0)

    def test_build_web_search_prompt_difficulty(self):
        """Prompt builder includes explicit target difficulty when specified."""
        prompt_mixed = _build_web_search_prompt("Python", 5, difficulty="mixed")
        self.assertIn("Mix difficulty across beginner, intermediate, and advanced", prompt_mixed)

        prompt_inter = _build_web_search_prompt("Python", 5, difficulty="intermediate")
        self.assertIn("Target difficulty: intermediate level specifically", prompt_inter)

    @patch("cert_app.agents.question_agent._call_web_search_llm")
    @patch("cert_app.agents.question_agent._call_llm_once")
    def test_generate_questions_beginner_does_not_call_web_search(self, mock_llm_once, mock_web_search):
        """Generating questions with difficulty='beginner' should not call web search LLM at all."""
        mock_llm_once.return_value = [
            {
                "question": f"Beginner Q{i}?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "expected_answer": "Exp",
                "difficulty": "beginner",
                "source": "llm",
            }
            for i in range(30)
        ]

        qs = generate_questions("Python", num_questions=30, difficulty="beginner")
        self.assertEqual(len(qs), 30)
        mock_web_search.assert_not_called()
        mock_llm_once.assert_called()

    @patch("cert_app.agents.question_agent.get_cached_web_search_questions")
    @patch("cert_app.agents.question_agent._get_raw_client")
    def test_web_search_llm_uses_cache(self, mock_raw_client, mock_get_cache):
        """_call_web_search_llm should return cached items without making live API calls."""
        mock_get_cache.return_value = [
            {
                "question": f"Cached Web Q{i}?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "expected_answer": "Exp",
                "difficulty": "intermediate",
                "source": "web_search",
            }
            for i in range(10)
        ]

        qs = _call_web_search_llm("Python", count=5, difficulty="intermediate")
        self.assertEqual(len(qs), 5)
        self.assertTrue(all(q["source"] == "web_search" for q in qs))
        mock_raw_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
