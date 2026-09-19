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
        "beginner": ("BEGINNER -- apply these as hard constraints", 0.65),
        "intermediate": ("INTERMEDIATE -- test application rather than basic recall", 0.8),
        "advanced": ("ADVANCED -- require deeper reasoning and informed judgment", 0.9),
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
        self.assertIn("exactly one basic concept", prompt)
        self.assertIn("no more than 18 words", prompt)
        self.assertIn("Do not combine concepts", prompt)
        self.assertIn("Do not ask multi-part questions", prompt)

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
                self.assertIn(
                    "reserve the others for potential follow-up questions",
                    prompt,
                )

    def test_new_subjects_receive_role_specific_prompt_guidance(self):
        digital_prompt = self._generate_and_capture(
            "beginner", "SEM & Google Ads"
        )["messages"][0]["content"]
        systems_prompt = self._generate_and_capture(
            "beginner", "Docker & Kubernetes"
        )["messages"][0]["content"]

        self.assertIn("campaign decisions", digital_prompt)
        self.assertIn("generic software-engineering interviews", digital_prompt)
        self.assertIn("reliably operating production systems", systems_prompt)
        self.assertIn("Connect the selected topic area directly", systems_prompt)

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
        self.assertIn(result["question"], groq_client.SAFE_HR_QUESTION_TEMPLATES["advanced"])
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

        for round_type, levels in groq_client.SAFE_FOLLOWUP_QUESTIONS.items():
            for difficulty, candidate in levels.items():
                with self.subTest(
                    kind=f"{round_type}_followup",
                    difficulty=difficulty,
                    candidate=candidate,
                ):
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
            "beginner": "Do not require formal work experience",
            "intermediate": "behavioral or situational HR question",
            "advanced": "leadership, ownership, conflict",
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
        response = {
            "follow_up_needed": False,
            "follow_up_question": None,
            **response,
        }
        capture = PromptCapture(json.dumps(response))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.evaluate_answer(question, answer, "beginner")
        return result, capture.calls[0]

    def test_technical_evaluation_combines_followup_decision_in_one_call(self):
        response = {
            "verdict": "partial",
            "reason": "You identified mutability but did not explain its practical effect.",
            "ideal_answer": "A mutable object can change after creation, affecting every reference to it.",
            "follow_up_needed": True,
            "follow_up_question": "How can mutability affect two references to the same object?",
        }
        capture = PromptCapture(json.dumps(response))
        with patch.object(groq_client, "_chat", side_effect=capture) as mocked_chat:
            result = groq_client.evaluate_answer(
                "What does mutability mean in Python?",
                "It means the value can change.",
                "intermediate",
                "technical",
            )

        self.assertEqual(mocked_chat.call_count, 1)
        self.assertTrue(result["follow_up_needed"])
        self.assertEqual(
            result["follow_up_question"],
            response["follow_up_question"],
        )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertIn('"follow_up_needed": true | false', prompt)
        self.assertIn("material conceptual gap", prompt)

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
            "follow_up_needed": False,
            "follow_up_question": None,
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
        self.assertFalse(result["follow_up_needed"])
        self.assertIsNone(result["follow_up_question"])
        self.assertIn("Do not require corporate buzzwords", prompt)
        self.assertIn("perfect STAR formatting", prompt)
        self.assertIn("final corrected meaning", prompt)
        self.assertIn(answer, capture.calls[0]["messages"][1]["content"])

    def test_hr_prompt_requests_followup_only_for_material_gap(self):
        capture = PromptCapture(json.dumps({
            "verdict": "partial",
            "reason": "You identified a deadline situation, but your specific actions remain unclear.",
            "ideal_answer": (
                "When our deadline moved forward, I prioritized the remaining tasks, divided "
                "the work with my team, and used daily check-ins so we submitted on time."
            ),
            "follow_up_needed": True,
            "follow_up_question": "What specific steps did you take to organize the work?",
        }))
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.evaluate_answer(
                "Describe a time you handled a difficult deadline.",
                "The deadline got close, so we worked on it and submitted.",
                "intermediate",
                "hr",
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertTrue(result["follow_up_needed"])
        self.assertIn("genuinely vague, off-topic, or incomplete", prompt)
        self.assertIn("optional detail", prompt)

    def test_hr_followup_contract_is_validated(self):
        capture = PromptCapture(json.dumps({
            "verdict": "partial",
            "reason": "Your example needs your specific action.",
            "ideal_answer": "I clarified the issue, agreed on priorities, and followed up.",
            "follow_up_needed": True,
            "follow_up_question": None,
        }))
        with (
            patch.object(groq_client, "_chat", side_effect=capture),
            self.assertRaisesRegex(ValueError, "invalid HR follow-up question"),
        ):
            groq_client.evaluate_answer(
                "Tell me about a conflict.",
                "We had a disagreement.",
                "beginner",
                "hr",
            )


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


class FollowupPromptTests(unittest.TestCase):
    def test_correct_answer_returns_none_with_supportive_followup_rules(self):
        capture = PromptCapture("NONE")
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.generate_followup(
                "What is a tuple?",
                "It is a locked collection that cannot be changed.",
                "beginner",
                "correct",
                "The concept is correct; immutable is the precise term.",
            )
        system_prompt = capture.calls[0]["messages"][0]["content"]
        user_prompt = capture.calls[0]["messages"][1]["content"]
        self.assertIsNone(result)
        self.assertIn("Return exactly NONE when the verdict is correct", system_prompt)
        self.assertIn("an example not requested", system_prompt)
        self.assertIn("Evaluation verdict: correct", user_prompt)
        self.assertIn("Difficulty: beginner", user_prompt)

    def test_hr_followup_does_not_demand_polish_or_star_format(self):
        capture = PromptCapture("NONE")
        with patch.object(groq_client, "_chat", side_effect=capture):
            result = groq_client.generate_followup(
                "Why do you want this job?",
                "Honestly I want experience, and your products have real users.",
                "beginner",
                "correct",
                "The motivation is relevant and connected to the role.",
                "hr",
            )
        prompt = capture.calls[0]["messages"][0]["content"]
        self.assertIsNone(result)
        self.assertIn("perfect STAR formatting", prompt)
        self.assertIn("genuinely vague, off-topic, or incomplete", prompt)

    def test_overly_complex_technical_followup_is_regenerated(self):
        valid_retry = "Which testing concern is most important for this dependency?"
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[FAILING_ADVANCED_QUESTION, valid_retry],
            ) as mocked_chat,
            self.assertLogs("llm_client", level="INFO") as logs,
        ):
            result = groq_client.generate_followup(
                "When would you choose an integration test?",
                "I would use one when dependencies interact.",
                "advanced",
                "partial",
                "The answer did not identify the main trade-off.",
                "technical",
            )

        self.assertEqual(result, valid_retry)
        self.assertEqual(mocked_chat.call_count, 2)
        self.assertFalse(
            groq_client._question_validation_errors(result, "advanced")
        )
        self.assertTrue(
            any("type=technical_followup" in entry for entry in logs.output)
        )

    def test_overly_complex_inline_hr_followup_is_regenerated(self):
        evaluation = json.dumps({
            "verdict": "partial",
            "reason": "The answer omitted the candidate's own action.",
            "ideal_answer": "I would explain my action and its result.",
            "follow_up_needed": True,
            "follow_up_question": FAILING_HR_QUESTION,
        })
        valid_retry = "What specific action did you take in that situation?"
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[evaluation, valid_retry],
            ) as mocked_chat,
            self.assertLogs("llm_client", level="INFO") as logs,
        ):
            result = groq_client.evaluate_answer(
                "Tell me about a disagreement with a teammate?",
                "We disagreed about the project.",
                "advanced",
                "hr",
            )

        self.assertEqual(result["follow_up_question"], valid_retry)
        self.assertEqual(mocked_chat.call_count, 2)
        self.assertFalse(
            groq_client._question_validation_errors(valid_retry, "advanced")
        )
        self.assertTrue(
            any("type=hr_inline_followup" in entry for entry in logs.output)
        )

    def test_followup_uses_safe_fallback_after_all_attempts_fail(self):
        with (
            patch.object(
                groq_client,
                "_chat",
                side_effect=[FAILING_ADVANCED_QUESTION] * 3,
            ) as mocked_chat,
            self.assertLogs("llm_client", level="ERROR") as logs,
        ):
            result = groq_client.generate_followup(
                "What trade-off matters most?",
                "Several things matter.",
                "advanced",
                "partial",
                "The answer is too broad.",
                "technical",
            )

        self.assertEqual(mocked_chat.call_count, 3)
        self.assertEqual(
            result,
            groq_client.SAFE_FOLLOWUP_QUESTIONS["technical"]["advanced"],
        )
        self.assertFalse(
            groq_client._question_validation_errors(result, "advanced")
        )
        self.assertTrue(any("using fallback" in entry for entry in logs.output))


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
