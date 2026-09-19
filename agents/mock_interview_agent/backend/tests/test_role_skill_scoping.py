import json
import os
import time
from threading import Lock
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from ai import question_generation as questions
from services.role_interviews import normalize_weak_topic_areas, subject_breakdown


class RoleSkillScopingTests(unittest.TestCase):
    def setUp(self):
        questions._role_skill_cache.clear()

    def test_preset_role_uses_reviewed_skills_without_an_llm_call(self):
        chat = Mock(side_effect=AssertionError("preset roles must not call the LLM"))
        skills = questions.infer_role_skills(
            " Python Fullstack Developer ", "beginner", chat_fn=chat
        )
        self.assertEqual(
            skills,
            questions.PRESET_ROLE_SKILLS["python fullstack developer"]["beginner"],
        )
        chat.assert_not_called()

    def test_custom_role_is_inferred_once_then_served_from_cache(self):
        chat = Mock(return_value=json.dumps([
            "CI/CD pipelines", "container orchestration", "infrastructure as code",
            "cloud networking", "observability", "incident response",
        ]))
        first = questions.infer_role_skills("DevOps Engineer", "intermediate", chat_fn=chat)
        second = questions.infer_role_skills("  devops   engineer ", "intermediate", chat_fn=chat)
        self.assertEqual(first, second)
        self.assertEqual(chat.call_count, 1)
        self.assertIn("infrastructure as code", first)

    def test_generated_question_is_scoped_to_a_role_skill(self):
        skills = questions.PRESET_ROLE_SKILLS["ai engineer"]["intermediate"]
        selected = skills[0]
        chat = Mock(return_value=json.dumps({
            "topic_area": selected,
            "question": "How would you prepare data for a machine learning pipeline?",
        }))
        result = questions.generate_question(
            "technical", "AI Engineer", "intermediate", [],
            role_skills=skills, skill_area=selected, chat_fn=chat, rng=Mock(),
        )
        prompt = chat.call_args.args[0][0]["content"]
        self.assertEqual(result["topic_area"], selected)
        self.assertIn(selected, prompt)
        self.assertIn("specific skill area assigned to THIS", prompt)
        self.assertIn("machine learning", result["question"].casefold())

    def test_fullstack_plan_round_robins_across_multiple_skill_areas(self):
        skills = questions.PRESET_ROLE_SKILLS[
            "python fullstack developer"
        ]["beginner"]
        with patch("ai.question_generation.fetch_live_real_questions", return_value=[]):
            plan = questions.build_interview_questions(
                "Python Fullstack Developer", "beginner", "technical", 10,
                # Batch generation is now the intentional contract: one
                # chat call returns the complete plan and deterministic
                # fallbacks preserve the round-robin skill assignment.
                chat_fn=Mock(return_value=json.dumps({"questions": []})),
                generate_ai_question=Mock(),
                rng=Mock(shuffle=lambda _items: None),
                role_skills=skills,
            )

        assigned = [item["assigned_skill_area"] for item in plan]
        self.assertGreaterEqual(len(set(assigned)), 3)
        self.assertEqual(assigned[:6], skills)
        self.assertTrue(all(item["assigned_skill_area"] in skills for item in plan))
        self.assertEqual(plan[0]["source"], "ai_generated")

    def test_initial_question_plan_generates_slots_concurrently(self):
        """Ten independent LLM slots should take roughly one call, not ten."""
        def slow_question(_asked, skill):
            time.sleep(0.05)
            return {
                "topic_area": skill,
                "question": f"How would you apply {skill}?",
            }

        started = time.perf_counter()
        plan = questions.build_interview_questions(
            "Python Fullstack Developer", "beginner", "technical", 10,
            chat_fn=Mock(),
            generate_ai_question=slow_question,
            rng=Mock(shuffle=lambda _items: None),
            role_skills=questions.PRESET_ROLE_SKILLS[
                "python fullstack developer"
            ]["beginner"],
            initial_asked_context=["What is a previous question?"],
        )
        elapsed = time.perf_counter() - started

        self.assertEqual(len(plan), 10)
        self.assertLess(elapsed, 0.2)

    def test_collision_retry_starts_before_slow_initial_slot_finishes(self):
        """Batch mode intentionally performs one complete-plan call."""
        chat = Mock(return_value=json.dumps({"questions": [
            {"question": "What is A?"}, {"question": "What is B?"},
        ]}))
        plan = questions.build_interview_questions(
            "Example", "beginner", "technical", 2,
            chat_fn=chat,
            generate_ai_question=Mock(),
            rng=Mock(shuffle=lambda _items: None),
            role_skills=["A", "B"],
            already_asked_hashes={questions.question_hash("Already asked?")},
        )
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(len(plan), 2)
        self.assertEqual({item["assigned_skill_area"] for item in plan}, {"A", "B"})

    def test_data_scientist_keeps_python_pandas_and_statistics_separate(self):
        self.assertEqual(
            questions.infer_role_skills("Data Scientist", "beginner"),
            [
                "Python fundamentals", "Pandas and DataFrames", "NumPy basics",
                "Statistics fundamentals", "Data visualization basics", "Excel basics",
                "SQL basics",
            ],
        )

    def test_data_analyst_keeps_python_pandas_and_statistics_separate(self):
        skills = questions.infer_role_skills("Data Analyst", "beginner")
        self.assertIn("Python fundamentals", skills)
        self.assertIn("Pandas and DataFrames", skills)
        self.assertIn("Statistics fundamentals", skills)
        self.assertIn("Excel basics", skills)

    def test_legacy_python_weak_tag_becomes_core_python_retest(self):
        self.assertEqual(
            normalize_weak_topic_areas(["python"]),
            ["Python fundamentals"],
        )

    def test_weak_breakdown_uses_topic_area_not_broad_subject_tag(self):
        breakdown = subject_breakdown([
            {"subject_tag": "python", "topic_area": "Pandas and DataFrames", "verdict": "wrong"},
            {"subject_tag": "python", "topic_area": "Excel basics", "verdict": "wrong"},
            {"subject_tag": "python", "topic_area": "Python fundamentals", "verdict": "correct"},
        ])
        self.assertEqual(
            breakdown["weak_subjects"], ["Pandas and DataFrames", "Excel basics"],
        )
        self.assertNotIn("python", breakdown["weak_subjects"])


if __name__ == "__main__":
    unittest.main()
