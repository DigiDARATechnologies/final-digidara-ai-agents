import unittest

import scoring


class ScoreAlignmentTests(unittest.TestCase):
    def test_knowledge_is_the_marks_share_out_of_ten(self):
        result = {"overall_score": 7, "technical_accuracy": 7, "communication_clarity": 6, "confidence": 6}
        scoring.align_scores_with_marks(result, 4, 5)
        self.assertEqual(result["technical_accuracy"], 8.0)
        # 0.7 * 8 + 0.3 * 6
        self.assertEqual(result["overall_score"], 7.4)

    def test_same_marks_give_the_same_knowledge_whatever_the_ai_said(self):
        first = {"overall_score": 9, "technical_accuracy": 9, "communication_clarity": 7, "confidence": 7}
        second = {"overall_score": 3, "technical_accuracy": 2, "communication_clarity": 7, "confidence": 7}
        scoring.align_scores_with_marks(first, 3, 5)
        scoring.align_scores_with_marks(second, 3, 5)
        self.assertEqual(first, second)

    def test_inflated_delivery_is_pulled_down_to_the_band(self):
        result = {"communication_clarity": 9, "confidence": 8}
        scoring.align_scores_with_marks(result, 1, 5)  # knowledge 2.0
        self.assertEqual(result["communication_clarity"], 5.0)
        self.assertEqual(result["confidence"], 5.0)
        self.assertEqual(result["overall_score"], 2.9)

    def test_delivery_inside_the_band_is_kept(self):
        result = {"communication_clarity": 6.5, "confidence": 5.5}
        scoring.align_scores_with_marks(result, 3.5, 5)  # knowledge 7.0
        self.assertEqual(result["communication_clarity"], 6.5)
        self.assertEqual(result["confidence"], 5.5)

    def test_all_wrong_scores_low_everywhere(self):
        result = {"communication_clarity": 8, "confidence": 8}
        scoring.align_scores_with_marks(result, 0, 4)
        self.assertEqual(result["technical_accuracy"], 0.0)
        self.assertEqual(result["communication_clarity"], 3.0)
        self.assertEqual(result["overall_score"], 0.9)

    def test_all_correct_scores_high(self):
        result = {"communication_clarity": 4, "confidence": 4}
        scoring.align_scores_with_marks(result, 5, 5)
        self.assertEqual(result["technical_accuracy"], 10.0)
        self.assertEqual(result["communication_clarity"], 7.0)
        self.assertEqual(result["overall_score"], 9.1)

    def test_no_questions_leaves_scores_untouched(self):
        result = {"overall_score": 6}
        scoring.align_scores_with_marks(result, 0, 0)
        self.assertEqual(result["overall_score"], 6)


if __name__ == "__main__":
    unittest.main()
