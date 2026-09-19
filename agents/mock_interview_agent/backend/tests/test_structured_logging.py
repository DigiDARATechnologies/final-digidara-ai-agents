import json
import logging
import unittest

from flask import Flask, g

from structured_logging import JsonLogFormatter


class StructuredLoggingTests(unittest.TestCase):
    def test_formatter_emits_required_request_correlation_fields(self):
        app = Flask(__name__)
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Evaluation failed",
            args=(),
            exc_info=None,
        )
        record.event = "answer_evaluation_failed"
        record.interview_id = 42

        with app.test_request_context("/api/submit_answer"):
            g.request_id = "request-123"
            g.student_id = 7
            payload = json.loads(formatter.format(record))

        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["student_id"], 7)
        self.assertEqual(payload["interview_id"], 42)
        self.assertEqual(payload["event"], "answer_evaluation_failed")
        self.assertEqual(payload["level"], "ERROR")
        self.assertIn("timestamp", payload)
        self.assertEqual(payload["message"], "Evaluation failed")

    def test_formatter_does_not_serialize_arbitrary_sensitive_extras(self):
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Safe message",
            args=(),
            exc_info=None,
        )
        record.api_key = "must-not-appear"
        record.session_token = "must-not-appear"

        output = formatter.format(record)
        self.assertNotIn("must-not-appear", output)
        self.assertNotIn("api_key", output)
        self.assertNotIn("session_token", output)


if __name__ == "__main__":
    unittest.main()
