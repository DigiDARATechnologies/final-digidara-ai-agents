import unittest

import scoring


class ScoreAlignmentTests(unittest.TestCase):
    def test_inflated_overall_score_is_pulled_down_to_the_marks(self):
        result = {"overall_score": 8.5, "technical_accuracy": 9, "communication_clarity": 8, "confidence": 7}
        scoring.align_scores_with_marks(result, 1, 5)  # marks say 2/10
        self.assertEqual(result["overall_score"], 3.5)
        self.assertEqual(result["technical_accuracy"], 3.5)
        # Delivery scores are not about correctness and stay as given.
        self.assertEqual(result["communication_clarity"], 8)
        self.assertEqual(result["confidence"], 7)

    def test_deflated_overall_score_is_pulled_up_to_the_marks(self):
        result = {"overall_score": 4, "technical_accuracy": 5}
        scoring.align_scores_with_marks(result, 5, 5)  # every answer correct
        self.assertEqual(result["overall_score"], 8.5)
        self.assertEqual(result["technical_accuracy"], 8.5)

    def test_score_inside_the_band_is_kept(self):
        result = {"overall_score": 6.8, "technical_accuracy": 7.2}
        scoring.align_scores_with_marks(result, 3.5, 5)  # 7/10
        self.assertEqual(result["overall_score"], 6.8)
        self.assertEqual(result["technical_accuracy"], 7.2)

    def test_all_wrong_cannot_score_above_the_tolerance(self):
        result = {"overall_score": 6, "technical_accuracy": 6}
        scoring.align_scores_with_marks(result, 0, 4)
        self.assertEqual(result["overall_score"], 1.5)

    def test_no_questions_leaves_scores_untouched(self):
        result = {"overall_score": 6}
        scoring.align_scores_with_marks(result, 0, 0)
        self.assertEqual(result["overall_score"], 6)


if __name__ == "__main__":
    unittest.main()
