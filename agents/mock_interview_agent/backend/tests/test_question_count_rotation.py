import json
import unittest
from unittest.mock import Mock

from ai.question_generation import build_interview_questions
from services.question_history import prioritize_skill_areas


class QuestionCountRotationTests(unittest.TestCase):
    def test_short_attempts_prioritize_uncovered_skills(self):
        skills = [f"Skill {index}" for index in range(1, 9)]
        first_order = prioritize_skill_areas(skills, [])
        first_attempt = first_order[:5]
        second_order = prioritize_skill_areas(skills, first_attempt)
        self.assertEqual(second_order[:3], skills[5:])
        self.assertEqual(second_order[:5], skills[5:] + skills[:2])

    def test_question_plan_supports_five_and_fifteen_slots(self):
        skills = [f"Skill {index}" for index in range(1, 7)]
        for count in (5, 15):
            plan = build_interview_questions(
                "Example Role", "beginner", "technical", count,
                chat_fn=Mock(return_value=json.dumps({"questions": []})),
                generate_ai_question=Mock(),
                rng=Mock(shuffle=lambda items: None),
                role_skills=skills,
                skill_order=skills,
            )
            self.assertEqual(len(plan), count)
            self.assertEqual(
                {item["assigned_skill_area"] for item in plan}, set(skills)
            )


if __name__ == "__main__":
    unittest.main()
