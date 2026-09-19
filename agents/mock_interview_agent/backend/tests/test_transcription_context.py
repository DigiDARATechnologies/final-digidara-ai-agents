import unittest
import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from ai import chat_client


class TranscriptionContextTests(unittest.TestCase):
    def test_python_question_context_is_sent_to_openai_prompt(self):
        create = Mock(return_value="A tuple in Python is an immutable collection.")
        fake_client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(create=create)
            )
        )

        with patch.object(chat_client, "client", fake_client), patch.object(
            chat_client, "record_provider_usage"
        ):
            transcript = chat_client.transcribe_audio(
                BytesIO(b"audio"),
                "answer.webm",
                "technical",
                subject="Python",
                question="What is a tuple in Python?",
            )

        self.assertEqual(
            transcript,
            "A tuple in Python is an immutable collection.",
        )
        options = create.call_args.kwargs
        self.assertIn("Technical interview about Python", options["prompt"])
        self.assertIn("What is a tuple in Python?", options["prompt"])
        self.assertIn("tuple", options["prompt"])
        self.assertEqual(options["model"], "gpt-4o-mini-transcribe")
        self.assertEqual(create.call_count, 1)

    def test_missing_context_omits_prompt_without_failing(self):
        create = Mock(return_value=SimpleNamespace(text="Fallback transcript"))
        fake_client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(create=create)
            )
        )

        with patch.object(chat_client, "client", fake_client), patch.object(
            chat_client, "record_provider_usage"
        ):
            transcript = chat_client.transcribe_audio(BytesIO(b"audio"))

        self.assertEqual(transcript, "Fallback transcript")
        self.assertNotIn("prompt", create.call_args.kwargs)
        self.assertEqual(create.call_count, 1)

    def test_custom_topic_uses_subject_and_question_without_keyword_call(self):
        prompt = chat_client.build_transcription_prompt(
            "technical",
            "Kubernetes Operators",
            "How does a reconciliation loop work?",
        )
        self.assertIn("Kubernetes Operators", prompt)
        self.assertIn("reconciliation loop", prompt)
        self.assertLess(len(prompt.split()), 120)


if __name__ == "__main__":
    unittest.main()
