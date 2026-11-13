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


def test_questions_must_include_what_they_refer_to():
    from cert_app.agents.question_agent import _validate_question

    def question(text, options=("A one", "B two", "C three", "D four")):
        return {"question": text, "options": list(options), "correct_answer": options[0]}

    assert not _validate_question(question("What is the main idea of the passage?"))
    assert not _validate_question(question("What is the average salary in the employees table?", ("5000", "6000", "7000", "8000")))
    assert not _validate_question(question("How many rows are in the orders table?", ("1", "2", "3", "4")))
    assert _validate_question(question("Which SQL clause groups rows in the employees table?", ("GROUP BY", "ORDER BY", "HAVING", "WHERE")))
    assert _validate_question(question("Table employees has rows: (1, 5000), (2, 7000). What is the average salary?", ("6000", "5000", "7000", "8000")))
    assert _validate_question(question("What does the SELECT statement do in SQL?"))


def test_the_same_question_reworded_is_a_duplicate():
    from cert_app.agents.question_agent import QuestionDeduper

    deduper = QuestionDeduper()
    assert deduper.add("What is the purpose of a primary key in SQL databases?")
    assert not deduper.add("In SQL databases, what is the purpose of the primary key?")
    assert deduper.add("What is the purpose of a foreign key constraint in joins?")
    assert deduper.add("What is the output of print(2 ** 3) in Python?")
    assert deduper.add("What is the output of print(3 ** 2) in Python?")


def test_career_courses_get_their_own_question_areas_not_code_ones():
    from cert_app.agents.question_agent import _focus_for, _MARKETING_FOCUS_AREAS, _PROMPT_FOCUS_AREAS, _GENERAL_FOCUS_AREAS

    marketing = {_focus_for("Digital Marketing", i) for i in range(8)}
    prompting = {_focus_for("Prompt Engineering", i) for i in range(8)}
    assert marketing == set(_MARKETING_FOCUS_AREAS) and prompting == set(_PROMPT_FOCUS_AREAS)
    assert not any("debugging" in area for area in marketing | prompting)
    assert _focus_for("Docker", 2) == _GENERAL_FOCUS_AREAS[2]


def test_both_career_courses_are_named_courses_on_the_certificate():
    from cert_app.services.exam_service import is_topic_course

    assert is_topic_course("Digital Marketing") and is_topic_course(" prompt engineering ")
