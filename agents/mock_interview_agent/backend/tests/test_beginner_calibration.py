"""Beginner technical prompts must set a simpler standard without changing other levels."""

import json
import random
import unittest

from ai.answer_evaluation import evaluate_answer, evaluate_answers_batch, evaluate_interview
from ai.question_generation import (
    HR_LEVEL_GUIDANCE,
    HR_QUESTION_AREAS,
    PRESET_ROLE_SKILLS,
    TECHNICAL_LEVEL_GUIDANCE,
    build_interview_questions,
    generate_question,
)
from ai.validators import (
    _beginner_technical_question_errors,
    _intermediate_technical_question_errors,
    _question_validation_errors,
    _safe_fallback_question,
)


class BeginnerCalibrationTests(unittest.TestCase):
    def test_role_batch_requests_ten_fundamental_questions(self):
        captured = []
        questions = [{"question": f"What is concept {index}?"} for index in range(1, 11)]

        def chat(messages, **_kwargs):
            captured.append(messages[0]["content"])
            return json.dumps({"questions": questions})

        plan = build_interview_questions(
            "Python Fullstack Developer", "beginner", "technical", 10,
            chat_fn=chat, generate_ai_question=lambda *_args: None,
            rng=random.Random(1), role_skills=["Python fundamentals", "SQL basics"],
        )
        self.assertEqual(len(plan), 10)
        self.assertEqual(len(captured), 1)
        self.assertIn("BEGINNER / FRESHER", captured[0])
        self.assertIn("RESTful architecture", captured[0])
        self.assertIn("settings.py", captured[0])
        self.assertIn("with statement", captured[0])

        for level in ("intermediate", "advanced"):
            captured.clear()
            build_interview_questions(
                "Python Fullstack Developer", level, "technical", 10,
                chat_fn=chat, generate_ai_question=lambda *_args: None,
                rng=random.Random(1), role_skills=["Python fundamentals"],
            )
            self.assertIn(TECHNICAL_LEVEL_GUIDANCE[level], captured[0])
            self.assertNotIn("BEGINNER / FRESHER", captured[0])

    def test_beginner_rejects_reported_advanced_question_types(self):
        rejected = (
            "What are the main principles of RESTful architecture?",
            "What is the purpose of the settings.py file in a Django project?",
            "What is the purpose of the with statement in Python?",
        )
        for question in rejected:
            with self.subTest(question=question):
                self.assertTrue(_beginner_technical_question_errors(question))
        for question in (
            "What is the purpose of CSS in web development?",
            "What does the git status command do?",
            "What is a SQL query used for?",
        ):
            self.assertFalse(_beginner_technical_question_errors(question))

    def test_batch_replaces_advanced_beginner_types_without_extra_ai_calls(self):
        bad = [
            "What are the main principles of RESTful architecture?",
            "What is the purpose of the settings.py file in a Django project?",
            "What is the purpose of the with statement in Python?",
        ]
        calls = []
        def chat(messages, **_kwargs):
            calls.append(messages)
            return json.dumps({"questions": [{"question": question} for question in bad]})
        plan = build_interview_questions(
            "Python Fullstack Developer", "beginner", "technical", 3,
            chat_fn=chat, generate_ai_question=lambda *_args: None,
            rng=random.Random(1),
            role_skills=["REST API basics", "Flask or Django basics", "Python fundamentals"],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(plan), 3)
        self.assertTrue(all(not _beginner_technical_question_errors(item["question"]) for item in plan))
        self.assertTrue(all(item["question"] not in bad for item in plan))

    def test_hr_prompts_are_distinct_at_each_level(self):
        examples = {
            "beginner": "Why are you interested in this opportunity?",
            "intermediate": "Tell me about a time you worked with a teammate?",
            "advanced": "How did you lead a team through uncertainty?",
        }
        for level, question in examples.items():
            prompts = []
            def chat(messages, **_kwargs):
                prompts.append(messages[0]["content"])
                from ai.question_generation import HR_QUESTION_AREAS
                return json.dumps({"topic_area": HR_QUESTION_AREAS[level][0], "question": question})
            generate_question("hr", None, level, [], chat_fn=chat, rng=random.Random(1))
            self.assertIn(HR_LEVEL_GUIDANCE[level], prompts[0])
            for other_level in set(examples) - {level}:
                self.assertNotIn(HR_LEVEL_GUIDANCE[other_level], prompts[0])

    def test_intermediate_rejects_advanced_or_coding_tasks(self):
        self.assertTrue(_intermediate_technical_question_errors(
            "How can you optimize a SQL query that is running slowly?"
        ))
        self.assertTrue(_intermediate_technical_question_errors(
            "How would you implement a context manager in Python?"
        ))
        self.assertTrue(_intermediate_technical_question_errors(
            "How would you implement token-based authentication in a REST API?"
        ))
        self.assertTrue(_intermediate_technical_question_errors(
            "What configuration settings are essential for deploying Flask in production?"
        ))
        self.assertFalse(_intermediate_technical_question_errors(
            "What are the key constraints of REST and why are they important?"
        ))

    def test_hr_fallbacks_remain_distinct_and_tier_appropriate(self):
        for level, areas in HR_QUESTION_AREAS.items():
            seen = []
            for area in areas:
                question = _safe_fallback_question(area, level, seen, round_type="hr")
                self.assertFalse(_question_validation_errors(question, level), question)
                self.assertNotIn(question, seen)
                seen.append(question)
            self.assertEqual(len(seen), 10)

    def test_full_intermediate_and_advanced_fallback_plans_are_unique(self):
        for level in ("intermediate", "advanced"):
            skills = PRESET_ROLE_SKILLS["python fullstack developer"][level]
            plan = build_interview_questions(
                "Python Fullstack Developer", level, "technical", 10,
                chat_fn=lambda *_args, **_kwargs: '{"questions":[]}',
                generate_ai_question=lambda *_args: None,
                rng=random.Random(42), role_skills=skills,
            )
            questions = [item["question"] for item in plan]
            self.assertEqual(len(set(questions)), 10)
            self.assertFalse(any("one core concept from this subject" in q for q in questions))

    def test_batch_and_final_scoring_prompts_match_all_six_tiers(self):
        batch_payload = {"evaluations": [{
            "question_id": 1, "verdict": "correct", "reason": "Relevant.",
            "ideal_answer": "A clear answer.",
        }]}
        final_payload = {
            "overall_score": 8, "technical_accuracy": 8,
            "communication_clarity": 8, "confidence": 8,
            "strengths": ["Clear", "Relevant"],
            "weaknesses": ["More detail", "More examples"],
            "feedback": "Keep practising.",
        }
        for round_type in ("technical", "hr"):
            for level in ("beginner", "intermediate", "advanced"):
                batch_prompts, final_prompts = [], []
                def batch_chat(messages, **_kwargs):
                    batch_prompts.append(messages[0]["content"])
                    return json.dumps(batch_payload)
                def final_chat(messages, **_kwargs):
                    final_prompts.append(messages[0]["content"])
                    return json.dumps(final_payload)
                pairs = [{"question_id": 1, "question": "Example?", "answer": "Answer."}]
                evaluate_answers_batch(round_type, "Python", level, pairs, chat_fn=batch_chat)
                evaluate_interview(round_type, "Python", level, pairs, chat_fn=final_chat)
                marker = f"{level.upper()}{' HR' if round_type == 'hr' else ''} SCORING"
                self.assertIn(marker, batch_prompts[0])
                self.assertIn(marker, final_prompts[0])

    def test_batch_evaluation_has_beginner_verdict_and_ideal_answer_rules(self):
        prompts = []

        def chat(messages, **_kwargs):
            prompts.append(messages[0]["content"])
            return json.dumps({"evaluations": [{
                "question_id": 1, "verdict": "correct", "reason": "Accurate.",
                "ideal_answer": "CSS styles HTML pages.",
            }]})

        pairs = [{"question_id": 1, "question": "What is CSS used for?", "answer": "CSS styles HTML pages."}]
        for level in ("beginner", "intermediate", "advanced"):
            evaluate_answers_batch("technical", "CSS", level, pairs, chat_fn=chat)
        self.assertIn("core idea is accurate", prompts[0])
        self.assertIn("Mark wrong for an incorrect, unrelated, or empty answer", prompts[0])
        self.assertIn("1-3 plain-language sentences", prompts[0])
        self.assertNotIn("BEGINNER TECHNICAL RUBRIC", prompts[1])
        self.assertNotIn("BEGINNER TECHNICAL RUBRIC", prompts[2])
        self.assertIn("INTERMEDIATE SCORING", prompts[1])
        self.assertIn("ADVANCED SCORING", prompts[2])

    def test_single_answer_and_summary_use_beginner_standard_only(self):
        prompts = []

        def single_chat(messages, **_kwargs):
            prompts.append(messages[0]["content"])
            return json.dumps({
                "verdict": "correct", "reason": "Accurate.",
                "ideal_answer": "A route connects a URL to a Flask function.",
            })

        evaluate_answer("What is a Flask route?", "It connects a URL to a function.", "beginner", chat_fn=single_chat)
        evaluate_answer("What is a Flask route?", "It connects a URL to a function.", "intermediate", chat_fn=single_chat)
        self.assertIn("BEGINNER TECHNICAL RUBRIC", prompts[0])
        self.assertNotIn("BEGINNER TECHNICAL RUBRIC", prompts[1])

        def summary_chat(messages, **_kwargs):
            prompts.append(messages[0]["content"])
            return json.dumps({
                "overall_score": 8, "technical_accuracy": 8,
                "communication_clarity": 8, "confidence": 8,
                "strengths": ["Clear", "Relevant"],
                "weaknesses": ["Add examples", "Keep practising"],
                "feedback": "Good foundation.",
            })

        evaluate_interview("technical", "Python", "beginner", [], chat_fn=summary_chat)
        evaluate_interview("technical", "Python", "advanced", [], chat_fn=summary_chat)
        self.assertIn("BEGINNER TECHNICAL RUBRIC", prompts[2])
        self.assertNotIn("BEGINNER TECHNICAL RUBRIC", prompts[3])


if __name__ == "__main__":
    unittest.main()
