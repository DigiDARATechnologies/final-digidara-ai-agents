import unittest
from datetime import datetime
from decimal import Decimal

from dashboard_logic import (
    build_dashboard_payload,
    build_improvement_payload,
)


def interview(
    interview_id,
    *,
    round_type="technical",
    subject="python",
    score=7,
    technical=6,
    communication=7,
    confidence=7,
    recent=False,
    this_month=False,
):
    day = max(1, 10 - interview_id)
    return {
        "id": interview_id,
        "round_type": round_type,
        "subject": subject if round_type == "technical" else None,
        "difficulty": "intermediate",
        "overall_score": Decimal(str(score)) if score is not None else None,
        "technical_accuracy": (
            Decimal(str(technical)) if technical is not None else None
        ),
        "communication_clarity": (
            Decimal(str(communication)) if communication is not None else None
        ),
        "confidence": Decimal(str(confidence)) if confidence is not None else None,
        "started_at": datetime(2026, 7, day),
        "completion_at": datetime(2026, 7, day, 12),
        "completed_last_7_days": recent,
        "started_this_month": this_month,
    }


class DashboardLogicTests(unittest.TestCase):
    def test_sql_improvement_aggregates_produce_available_percentage(self):
        improvement = build_improvement_payload(
            scored_count=10,
            recent_count=5,
            recent_average=Decimal("6.9"),
            earlier_average=Decimal("5.2"),
        )
        self.assertEqual(improvement["status"], "available")
        self.assertEqual(improvement["percentage"], 32.7)
        self.assertEqual(improvement["label"], "+32.7% improvement")

    def test_improvement_uses_unrounded_group_averages(self):
        improvement = build_improvement_payload(
            scored_count=14,
            recent_count=5,
            recent_average=Decimal("6.000000"),
            earlier_average=Decimal("5.977777"),
        )
        self.assertEqual(improvement["status"], "available")
        self.assertEqual(improvement["recent_average"], 6.0)
        self.assertEqual(improvement["earlier_average"], 5.98)
        self.assertEqual(improvement["percentage"], 0.4)
        self.assertEqual(improvement["label"], "+0.4% improvement")

    def test_empty_student_gets_complete_safe_payload(self):
        payload = build_dashboard_payload([])
        self.assertEqual(payload["total_interviews"], 0)
        self.assertIsNone(payload["average_score"])
        self.assertEqual(payload["weekly_practice_count"], 0)
        self.assertEqual(payload["recent_interviews"], [])
        self.assertEqual(payload["skill_performance_trend"], [])
        self.assertEqual(
            payload["improvement"]["status"],
            "not_enough_data",
        )

    def test_one_interview_hides_improvement_without_breaking_metrics(self):
        payload = build_dashboard_payload([
            interview(1, score=8, recent=True, this_month=True),
        ])
        self.assertEqual(payload["total_interviews"], 1)
        self.assertEqual(payload["average_score"], 8)
        self.assertEqual(payload["highest_score"], 8)
        self.assertEqual(payload["recent_interview_score"], 8)
        self.assertEqual(payload["weekly_practice_count"], 1)
        self.assertEqual(payload["interviews_this_month"], 1)
        self.assertEqual(
            payload["improvement"]["label"],
            "Not enough data yet",
        )

    def test_all_requested_metrics_use_completed_row_values(self):
        rows = [
            interview(
                1,
                subject="python",
                score=8,
                technical=7,
                communication=8,
                recent=True,
                this_month=True,
            ),
            interview(
                2,
                round_type="hr",
                score=7,
                technical=9,
                communication=9,
                recent=True,
                this_month=True,
            ),
            interview(
                3,
                subject="mysql",
                score=6,
                technical=5,
                communication=7,
                this_month=True,
            ),
            interview(
                4,
                round_type="hr",
                score=5,
                technical=None,
                communication=6,
            ),
        ]
        payload = build_dashboard_payload(rows)

        self.assertEqual(payload["total_interviews"], 4)
        self.assertEqual(payload["average_score"], 6.5)
        self.assertEqual(payload["highest_score"], 8)
        self.assertEqual(payload["recent_interview_score"], 8)
        self.assertEqual(payload["technical_performance"], 7)
        self.assertEqual(payload["communication_performance"], 7.5)
        self.assertEqual(payload["weekly_practice_count"], 2)
        self.assertEqual(payload["interviews_this_month"], 3)
        self.assertEqual(payload["improvement"]["percentage"], 36.4)
        self.assertEqual(len(payload["recent_interviews"]), 4)
        self.assertEqual(payload["recent_interviews"][0]["id"], 1)
        self.assertEqual(len(payload["skill_performance_trend"]), 4)
        self.assertEqual(payload["skill_performance_trend"][0]["id"], 4)
        self.assertEqual(
            payload["recommended_next_interview"]["subject"],
            "mysql",
        )


if __name__ == "__main__":
    unittest.main()
