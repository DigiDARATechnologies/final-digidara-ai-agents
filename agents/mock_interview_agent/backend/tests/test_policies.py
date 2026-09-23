import unittest

from policies import (
    completion_progress,
    counts_toward_daily_limit,
    exit_transition,
    integrity_flagged,
)


class DailyQuotaPolicyTests(unittest.TestCase):
    def test_only_answered_main_questions_count(self):
        self.assertTrue(counts_toward_daily_limit(
            enabled=True, is_followup=False, has_answer=True
        ))
        self.assertFalse(counts_toward_daily_limit(
            enabled=True, is_followup=True, has_answer=True
        ))
        self.assertFalse(counts_toward_daily_limit(
            enabled=True, is_followup=False, has_answer=False
        ))

    def test_disabled_limit_never_counts(self):
        self.assertFalse(counts_toward_daily_limit(
            enabled=False, is_followup=False, has_answer=True
        ))


class InterviewLifecyclePolicyTests(unittest.TestCase):
    def test_completion_requires_every_configured_main_question(self):
        rows = [
            {"is_followup": False, "verdict": "correct"},
            {"is_followup": True, "verdict": "partial"},
            {"is_followup": False, "verdict": None},
        ]

        progress = completion_progress(rows, 2)

        self.assertEqual(progress["answered_main_questions"], 1)
        self.assertEqual(progress["required_main_questions"], 2)
        self.assertFalse(progress["complete"])

    def test_completion_ignores_followups_and_accepts_evaluated_timeouts(self):
        rows = [
            {"is_followup": False, "verdict": "correct"},
            {"is_followup": True, "verdict": None},
            {"is_followup": False, "verdict": "wrong", "timed_out": True},
        ]

        self.assertTrue(completion_progress(rows, 2)["complete"])

    def test_exit_transition_reports_the_actual_current_state(self):
        self.assertEqual(exit_transition("in_progress"), "exit")
        self.assertEqual(exit_transition("exited"), "already_exited")
        self.assertEqual(exit_transition("completed"), "not_exit_eligible")


class InterviewIntegrityPolicyTests(unittest.TestCase):
    def test_flag_threshold_is_four_events_or_sixty_seconds(self):
        self.assertFalse(integrity_flagged(3, 59))
        self.assertTrue(integrity_flagged(4, 59))
        self.assertTrue(integrity_flagged(1, 60))

if __name__ == "__main__":
    unittest.main()
