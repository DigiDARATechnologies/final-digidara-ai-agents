"""OpenAI transport coverage for generated interview questions."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import groq_client
from ai import chat_client


class OpenAIQuestionGenerationTests(unittest.TestCase):
    def test_openai_completion_generates_expected_question_shape(self):
        completion = Mock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({
                                "topic_area": "variables and data types",
                                "question": "What is the difference between a string and an integer in Python?",
                            })
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=12),
            )
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=completion))
        )
        fake_client.with_options = Mock(return_value=fake_client)

        with (
            patch.object(chat_client, "MODEL", "gpt-4o-mini"),
            patch.object(chat_client, "client", fake_client),
            patch.object(chat_client, "record_provider_usage"),
        ):
            result = groq_client.generate_question(
                "technical", "Python", "beginner", []
            )

        self.assertEqual(result["topic_area"], "variables and data types")
        self.assertIn("string", result["question"])
        self.assertEqual(completion.call_args.kwargs["model"], "gpt-4o-mini")
        self.assertEqual(
            completion.call_args.kwargs["response_format"], {"type": "json_object"}
        )
        fake_client.with_options.assert_called_with(timeout=10.0, max_retries=0)

    def test_gpt5_chat_omits_unsupported_non_default_temperature(self):
        completion = Mock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=completion))
        )

        with (
            patch.object(chat_client, "MODEL", "gpt-5-mini"),
            patch.object(chat_client, "client", fake_client),
            patch.object(chat_client, "record_provider_usage"),
        ):
            chat_client.chat([{"role": "user", "content": "Return JSON."}], json_mode=True, temperature=0.65)

        self.assertNotIn("temperature", completion.call_args.kwargs)

    def test_evaluation_facade_routes_to_eval_model(self):
        captured = Mock(return_value=json.dumps({
            "verdict": "correct", "reason": "Accurate.",
            "ideal_answer": "The same concept.",
        }))
        with patch.object(groq_client, "EVAL_MODEL", "gpt-5-mini"), patch.object(groq_client, "_chat", captured):
            result = groq_client.evaluate_answer("What is a list?", "An ordered collection.", "beginner")
        self.assertEqual(result["verdict"], "correct")
        self.assertEqual(captured.call_args.kwargs["model_override"], "gpt-5-mini")

    def test_generation_and_evaluation_defaults_are_independent(self):
        self.assertEqual(chat_client.MODEL, "gpt-4o-mini")
        self.assertEqual(chat_client.EVAL_MODEL, "gpt-5-mini")

    def test_question_timeout_uses_immediate_safe_fallback(self):
        with patch.object(groq_client, "_chat", side_effect=TimeoutError("slow")):
            result = groq_client.generate_question(
                "technical", "Python", "beginner", []
            )

        self.assertEqual(result["topic_area"], "variables and data types")
        self.assertIn("Python", result["question"])


if __name__ == "__main__":
    unittest.main()
