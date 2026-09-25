import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

with patch("openai.OpenAI", return_value=object()):
    import groq_client


class PromptCapture:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, messages, json_mode=False, temperature=0.7, **_kwargs):
        self.calls.append({
            "messages": messages,
            "json_mode": json_mode,
            "temperature": temperature,
        })
        return self.response


FAILING_ADVANCED_QUESTION = (
    "What are the key considerations and trade-offs when choosing between "
    "unit tests and integration tests in Python, and how would you decide "
    "which type of test to write for a given piece of functionality, "
    "considering factors such as test isolation, test coverage, performance, "
    "and maintainability, especially in a large-scale application with "
    "complex dependencies and interactions between components?"
)
FAILING_HR_QUESTION = (
    "Tell me about a time you managed conflict with a teammate, and how you balanced "
    "deadlines, stakeholder expectations, team morale, performance concerns, and long-term "
    "relationships, while also considering accountability and communication across the organization?"
)


class QuestionGenerationPromptTests(unittest.TestCase):
    LEVELS = {
        "beginner": ("BEGINNER / FRESHER", 0.65),
        "intermediate": ("INTERMEDIATE: Assume basic definitions", 0.8),
        "advanced": ("ADVANCED: Test informed judgment", 0.9),
    }

    def _generate_and_capture(self, difficulty, subject):
        topic_area = (
            "variables and data types"
            if subject.casefold() in groq_client.PRESET_SUBJECTS
            else "operator reconciliation"
        )
        capture = PromptCapture(json.dumps({
            "topic_area": topic_area,
            "question": "What is this concept used for?",
        }))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.generate_question(
                "technical",
                subject,
                difficulty,
                asked_so_far=["Previous question?"],
            )
        self.assertEqual(result["topic_area"], topic_area)
        self.assertEqual(result["question"], "What is this concept used for?")
        self.assertTrue(capture.calls[0]["json_mode"])
        return capture.calls[0]

    def test_each_difficulty_has_distinct_hard_calibration_and_temperature(self):
        for difficulty, (expected_rule, expected_temperature) in self.LEVELS.items():
            with self.subTest(difficulty=difficulty):
                call = self._generate_and_capture(difficulty, "python")
                prompt = call["messages"][0]["content"]
                self.assertIn(expected_rule, prompt)
                self.assertIn(
                    "Difficulty constraints override variety hints",
                    prompt,
                )
                self.assertIn(
                    "never escalate into the next level",
                    prompt,
                )
                self.assertEqual(call["temperature"], expected_temperature)

    def test_beginner_prompt_enforces_one_short_single_concept_question(self):
        call = self._generate_and_capture("beginner", "python")
        prompt = call["messages"][0]["content"]
        self.assertIn("exactly one everyday foundational concept", prompt)
        self.assertIn("under 18 words", prompt)
        self.assertIn("RESTful architecture", prompt)
        self.assertIn("settings.py", prompt)
        self.assertIn("with statement", prompt)

    def test_custom_topics_receive_every_difficulty_branch(self):
        for difficulty, (expected_rule, _) in self.LEVELS.items():
            with self.subTest(difficulty=difficulty):
                call = self._generate_and_capture(difficulty, "Kubernetes Operators")
                prompt = call["messages"][0]["content"]
                self.assertIn(expected_rule, prompt)
                self.assertIn(
                    "<topic>Kubernetes Operators</topic>",
                    prompt,
                )
                self.assertIn(
                    "keep it strictly within its scope",
                    prompt,
                )

    def test_all_technical_subject_paths_enforce_the_same_concept_limit(self):
        for subject in (
            "python",
            "react",
            "SEO",
            "MLOps",
            "Kubernetes",
        ):
            with self.subTest(subject=subject):
                call = self._generate_and_capture("advanced", subject)
                prompt = call["messages"][0]["content"]
                self.assertIn(
                    "Never combine more than 2 distinct technical concepts",
                    prompt,
                )
                self.assertIn(
                    "pick ONE to focus the question on",
                    prompt,
                )
                self.assertNotIn("follow-up question", prompt)

    def test_new_subjects_receive_role_specific_prompt_guidance(self):
        digital_prompt = self._generate_and_capture(
            "beginner", "SEM & Google Ads"
        )["messages"][0]["content"]
        systems_prompt = self._generate_and_capture(
            "beginner", "Docker & Kubernetes"
        )["messages"][0]["content"]

        self.assertIn("marketing, cloud, and systems topics", digital_prompt)
        self.assertIn("not the most specialized item", digital_prompt)
        self.assertIn("Docker container", systems_prompt)
        self.assertIn("directly tied to the selected topic", systems_prompt)

    def test_validator_rejects_overly_complex_advanced_question(self):
        errors = groq_client._question_validation_errors(
            FAILING_ADVANCED_QUESTION,
            "advanced",
        )
        self.assertTrue(any("word count" in error for error in errors))
        self.assertTrue(
            any("comma-separated" in error for error in errors)
        )
        self.assertTrue(
            any("complexity markers" in error for error in errors)
        )

    def test_invalid_question_is_regenerated_before_return(self):
        valid_retry = (
            "When should Python integration tests be preferred over unit "
            "tests for dependency-heavy behavior?"
        )
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[
                    json.dumps({
                        "topic_area": "variables and data types",
                        "question": FAILING_ADVANCED_QUESTION,
                    }),
                    json.dumps({
                        "topic_area": "variables and data types",
                        "question": valid_retry,
                    }),
                ],
            ) as mocked_chat,
            self.assertLogs("llm_client", level="INFO") as logs,
        ):
            result = groq_client.generate_question(
                "technical",
                "python",
                "advanced",
                asked_so_far=[],
            )

        self.assertEqual(result["question"], valid_retry)
        self.assertEqual(mocked_chat.call_count, 2)
        retry_prompt = mocked_chat.call_args_list[1].args[0][0]["content"]
        self.assertIn("previous JSON response was rejected", retry_prompt)
        self.assertTrue(
            any(
                "Structured question regeneration succeeded" in entry
                for entry in logs.output
            )
        )

    def test_overly_complex_hr_question_is_regenerated_before_return(self):
        valid_retry = "Tell me about a time you resolved a disagreement with a teammate?"
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[
                    json.dumps({
                        "topic_area": "leadership",
                        "question": FAILING_HR_QUESTION,
                    }),
                    json.dumps({
                        "topic_area": "leadership",
                        "question": valid_retry,
                    }),
                ],
            ) as mocked_chat,
            self.assertLogs("llm_client", level="INFO") as logs,
        ):
            result = groq_client.generate_question(
                "hr",
                None,
                "advanced",
                asked_so_far=[],
            )

        self.assertEqual(result["question"], valid_retry)
        self.assertEqual(mocked_chat.call_count, 2)
        retry_prompt = mocked_chat.call_args_list[1].args[0][0]["content"]
        self.assertIn("previous JSON response was rejected", retry_prompt)
        self.assertFalse(
            groq_client._question_validation_errors(result["question"], "advanced")
        )
        self.assertTrue(
            any("type=hr_main" in entry for entry in logs.output)
        )

    def test_hr_fallback_bank_is_used_after_all_attempts_fail(self):
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[json.dumps({
                    "topic_area": "leadership",
                    "question": FAILING_HR_QUESTION,
                })] * 3,
            ) as mocked_chat,
            self.assertLogs("llm_client", level="ERROR") as logs,
        ):
            result = groq_client.generate_question(
                "hr",
                None,
                "advanced",
                asked_so_far=[],
            )

        self.assertEqual(mocked_chat.call_count, 3)
        self.assertEqual(result["topic_area"], "leadership")
        self.assertEqual(
            result["question"],
            "How did you lead a team through resistance to a difficult change?",
        )
        self.assertFalse(
            groq_client._question_validation_errors(result["question"], "advanced")
        )
        self.assertTrue(any("using fallback" in entry for entry in logs.output))

    def test_every_safe_question_template_passes_its_validator_tier(self):
        for difficulty, templates in groq_client.SAFE_HR_QUESTION_TEMPLATES.items():
            for candidate in templates:
                with self.subTest(kind="hr_main", difficulty=difficulty, candidate=candidate):
                    self.assertFalse(
                        groq_client._question_validation_errors(candidate, difficulty)
                    )

    def test_fallback_is_used_after_all_attempts_fail(self):
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[json.dumps({
                    "topic_area": "variables and data types",
                    "question": FAILING_ADVANCED_QUESTION,
                })] * 3,
            ) as mocked_chat,
            self.assertLogs("llm_client", level="ERROR") as logs,
        ):
            result = groq_client.generate_question(
                "technical",
                "python",
                "advanced",
                asked_so_far=[],
            )

        self.assertEqual(mocked_chat.call_count, 3)
        self.assertFalse(
            groq_client._question_validation_errors(result["question"], "advanced")
        )
        self.assertTrue(
            any("using fallback" in entry for entry in logs.output)
        )

    def test_hr_prompt_ignores_subject_and_contains_no_technical_variety_hint(self):
        area = "candidate introduction and background"
        question = "Could you briefly introduce yourself?"
        capture = PromptCapture(json.dumps({"topic_area": area, "question": question}))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.generate_question(
                "hr",
                "Python",
                "beginner",
                asked_so_far=["Why do you want this job?"],
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertEqual(
            result,
            {"topic_area": area, "question": question},
        )
        self.assertIn("HR or behavioral interview", prompt)
        self.assertIn(f"focus on this HR area: {area}", prompt)
        self.assertIn("Do not use or mention any technical subject", prompt)
        self.assertNotIn("Python", prompt)
        self.assertNotIn("variables and data types", prompt)
        self.assertNotIn("vector embedding", prompt)
        self.assertEqual(capture.calls[0]["temperature"], 0.65)

    def test_hr_difficulty_branches_are_behavioral(self):
        expectations = {
            "beginner": "Do not demand formal employment",
            "intermediate": "behavioral or situational question",
            "advanced": "leadership, complex conflict resolution",
        }
        for difficulty, expected in expectations.items():
            with self.subTest(difficulty=difficulty):
                area = groq_client.HR_QUESTION_AREAS[difficulty][0]
                capture = PromptCapture(json.dumps({
                    "topic_area": area,
                    "question": "Could you describe a relevant experience?",
                }))
                with patch.object(groq_client, "_chat", side_effect=capture):
                    groq_client.generate_question(
                        "hr",
                        None,
                        difficulty,
                        asked_so_far=[],
                    )
                prompt = capture.calls[0]["messages"][0]["content"]
                self.assertIn(expected, prompt)
                self.assertIn("genuine HR interview question", prompt)
                self.assertNotIn("selected technology stack", prompt)
                self.assertNotIn("foundational topic instead", prompt)

    def test_question_generator_rejects_invalid_round_and_subjectless_technical(self):
        with self.assertRaisesRegex(ValueError, "Unsupported round type"):
            groq_client.generate_question("sales", None, "beginner", [])
        with self.assertRaisesRegex(ValueError, "requires a subject"):
            groq_client.generate_question("technical", None, "beginner", [])


class AnswerEvaluationPromptTests(unittest.TestCase):
    def _evaluate_and_capture(self, question, answer, response):
        capture = PromptCapture(json.dumps(response))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.evaluate_answer(question, answer, "beginner")
        return result, capture.calls[0]

    def test_technical_evaluation_requests_only_verdict_reason_and_ideal_answer(self):
        response = {
            "verdict": "partial",
            "reason": "The answer misses the practical effect.",
            "ideal_answer": "A mutable object can change after creation.",
        }
        capture = PromptCapture(json.dumps(response))
        with patch.object(groq_client, "_chat", side_effect=capture) as mocked_chat:
            result = groq_client.evaluate_answer("What is mutability?", "It can change.", "intermediate")
        self.assertEqual(mocked_chat.call_count, 1)
        self.assertEqual(result, response)
        self.assertNotIn("follow_up", capture.calls[0]["messages"][0]["content"])

    def test_rambling_list_tuple_answer_is_treated_as_conceptual_answer(self):
        answer = (
            "Um, a list is... sorry, sorry, I mean lists can be changed, "
            "and tuples are locked and cannot be changed."
        )
        result, call = self._evaluate_and_capture(
            "What is the difference between a list and a tuple in Python?",
            answer,
            {
                "verdict": "correct",
                "reason": (
                    "Exactly right—the list is mutable while the tuple is immutable, "
                    "despite the informal wording."
                ),
                "ideal_answer": (
                    "Lists are mutable, while tuples cannot be changed after creation."
                ),
            },
        )
        system_prompt = call["messages"][0]["content"]
        user_prompt = call["messages"][1]["content"]
        self.assertEqual(result["verdict"], "correct")
        self.assertIn("final corrected meaning", system_prompt)
        self.assertIn("Ignore filler words", system_prompt)
        self.assertIn(answer, user_prompt)
        self.assertTrue(call["json_mode"])

    def test_correct_scope_lifetime_concept_accepts_informal_folder_term(self):
        answer = (
            "Scope is like the folder or area where the variable can be accessed, "
            "while lifetime is how long it remains available."
        )
        result, call = self._evaluate_and_capture(
            "Explain the difference between a variable's scope and lifetime.",
            answer,
            {
                "verdict": "correct",
                "reason": (
                    "Good explanation—the concept is correct; accessible region is "
                    "more precise than folder."
                ),
                "ideal_answer": (
                    "Scope is where a variable is accessible; lifetime is how long it exists."
                ),
            },
        )
        system_prompt = call["messages"][0]["content"]
        self.assertEqual(result["verdict"], "correct")
        self.assertIn("informal word", system_prompt)
        self.assertIn("offer the precise term as a helpful refinement", system_prompt)

    def test_prompt_still_reserves_wrong_for_genuine_misunderstanding(self):
        result, call = self._evaluate_and_capture(
            "What does break do in a loop?",
            "It restarts the loop from the beginning.",
            {
                "verdict": "wrong",
                "reason": (
                    "Good attempt, but break exits the loop rather than restarting it."
                ),
                "ideal_answer": "Break immediately exits the nearest enclosing loop.",
            },
        )
        self.assertEqual(result["verdict"], "wrong")
        self.assertIn(
            "Friendliness must not turn a genuinely incorrect or confused answer",
            call["messages"][0]["content"],
        )

    def test_evaluator_requests_full_natural_answer_and_keeps_beginner_depth(self):
        ideal_answer = (
            "A docstring documents the purpose and expected use of a module, class, "
            "function, or method. Python stores it in the object's __doc__ attribute, "
            "so tools such as help() can display that documentation."
        )
        result, call = self._evaluate_and_capture(
            "What is a docstring in Python?",
            "It is text below a function that explains it.",
            {
                "verdict": "correct",
                "reason": "Correct idea; documentation string is the precise term.",
                "ideal_answer": ideal_answer,
            },
        )
        prompt = call["messages"][0]["content"]
        self.assertIn("well-prepared candidate speaking naturally", prompt)
        self.assertIn("not a dictionary definition", prompt)
        self.assertIn("Use one or two clear, complete sentences", prompt)
        self.assertEqual(result["ideal_answer"], ideal_answer)

    def test_hr_prompt_judges_meaning_without_corporate_polish(self):
        answer = (
            "Um, mainly I want experience, honestly, but your team builds things "
            "real customers use and I want to learn from people doing that professionally."
        )
        capture = PromptCapture(json.dumps({
            "verdict": "correct",
            "reason": "Your honest motivation connects learning with the team's real-world work.",
            "ideal_answer": (
                "I want to apply my project experience to products used by real customers "
                "while learning from an experienced team and contributing what I already know."
            ),
        }))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.evaluate_answer(
                "Why do you want this job?",
                answer,
                "beginner",
                "hr",
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertEqual(result["verdict"], "correct")
        self.assertIn("Do not require corporate buzzwords", prompt)
        self.assertIn("perfect STAR formatting", prompt)
        self.assertIn("final corrected meaning", prompt)
        self.assertIn(answer, capture.calls[0]["messages"][1]["content"])



class IdealAnswerGenerationPromptTests(unittest.TestCase):
    LEVEL_EXPECTATIONS = {
        "beginner": "Use one or two clear, complete sentences",
        "intermediate": "Use two or three connected sentences",
        "advanced": "Use two to four focused sentences",
    }

    def test_timeout_generator_uses_same_difficulty_matched_guidance(self):
        for difficulty, expected in self.LEVEL_EXPECTATIONS.items():
            with self.subTest(difficulty=difficulty):
                capture = PromptCapture("A complete interview-quality answer.")
                with patch.object(groq_client, "_chat", side_effect=capture):
                    result = groq_client.generate_ideal_answer(
                        "What is scope in Python?",
                        difficulty,
                    )
                prompt = capture.calls[0]["messages"][0]["content"]
                self.assertEqual(result, "A complete interview-quality answer.")
                self.assertIn(expected, prompt)
                self.assertIn("not a dictionary definition", prompt)
                self.assertIn(
                    "provide a complete explanatory answer rather than a clipped phrase",
                    prompt,
                )

    def test_hr_timeout_answer_uses_natural_behavioral_guidance(self):
        capture = PromptCapture("I would clarify the feedback, act on it, and follow up.")
        with patch.object(groq_client, "_chat", side_effect=capture):
            groq_client.generate_ideal_answer(
                "How do you respond to feedback?",
                "intermediate",
                "hr",
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertIn("interview-recommended HR answer", prompt)
        self.assertIn("not a memorized corporate script", prompt)
        self.assertNotIn("accurate technical terminology", prompt)


class FinalEvaluationPromptTests(unittest.TestCase):
    def test_hr_final_score_uses_behavioral_not_technical_rubric(self):
        capture = PromptCapture(json.dumps({
            "overall_score": 8,
            "technical_accuracy": 8,
            "communication_clarity": 8,
            "confidence": 7,
            "strengths": [
                "Relevant and thoughtful examples.",
                "Clear ownership of the candidate's actions.",
            ],
            "weaknesses": [
                "Some results could be clearer.",
                "Responses could be more concise.",
            ],
            "feedback": "Add a concise result when describing major examples.",
        }))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.evaluate_interview(
                "hr",
                None,
                "intermediate",
                [{"question": "Tell me about a conflict.", "answer": "We discussed priorities."}],
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertIn("expert HR and behavioral interview evaluator", prompt)
        self.assertIn("does not represent technical knowledge", prompt)
        self.assertIn("imperfect structure", prompt)
        self.assertIn("2 to 4 distinct, concise points", prompt)
        self.assertEqual(
            json.loads(result["strengths"]),
            [
                "Relevant and thoughtful examples.",
                "Clear ownership of the candidate's actions.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
