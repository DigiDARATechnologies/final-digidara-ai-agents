import unittest

from validation import (
    ValidationError,
    boolean,
    bounded_int,
    email,
    positive_int,
    text,
)


class ValidationTests(unittest.TestCase):
    def test_positive_int_rejects_non_positive_values(self):
        for value in (0, -1, True, None, "bad"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    positive_int(value, "student_id")

    def test_boolean_rejects_truthy_non_booleans(self):
        self.assertTrue(boolean(True, "timed_out"))
        with self.assertRaises(ValidationError):
            boolean("false", "timed_out")

    def test_bounded_int_enforces_range(self):
        self.assertEqual(bounded_int("10", "count", 1, 10), 10)
        with self.assertRaises(ValidationError):
            bounded_int(11, "count", 1, 10)

    def test_text_enforces_type_and_length(self):
        self.assertEqual(text("  React  ", "topic", required=True), "React")
        with self.assertRaises(ValidationError):
            text(123, "topic")
        with self.assertRaises(ValidationError):
            text("abcd", "topic", max_length=3)

    def test_email_validation(self):
        self.assertEqual(email("student@example.com"), "student@example.com")
        with self.assertRaises(ValidationError):
            email("not-an-email")


if __name__ == "__main__":
    unittest.main()
