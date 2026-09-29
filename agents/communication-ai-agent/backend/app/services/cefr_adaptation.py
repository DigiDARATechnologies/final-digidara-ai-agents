"""Adaptive CEFR Calibration Service for Communication Coach.

Dynamically maps student performance trends across CEFR levels (A1 -> C2)
and computes adaptive difficulty recommendation without disrupting the
classic 'easy' | 'medium' | 'hard' parameters.
"""

from typing import Dict, List, Optional

# CEFR Scale definition with target capabilities and lexical complexity
CEFR_LEVELS = [
    {
        "code": "A1",
        "name": "Beginner",
        "min_score": 0.0,
        "max_score": 4.5,
        "difficulty_mapping": "easy",
        "description": "Can understand and use familiar everyday expressions and very basic phrases.",
    },
    {
        "code": "A2",
        "name": "Elementary",
        "min_score": 4.5,
        "max_score": 6.0,
        "difficulty_mapping": "easy",
        "description": "Can communicate in simple and routine tasks requiring a simple and direct exchange of information.",
    },
    {
        "code": "B1",
        "name": "Intermediate",
        "min_score": 6.0,
        "max_score": 7.5,
        "difficulty_mapping": "medium",
        "description": "Can understand the main points of clear standard input on familiar matters regularly encountered.",
    },
    {
        "code": "B2",
        "name": "Upper-Intermediate",
        "min_score": 7.5,
        "max_score": 8.5,
        "difficulty_mapping": "medium",
        "description": "Can interact with a degree of fluency and spontaneity that makes regular interaction with native speakers quite possible.",
    },
    {
        "code": "C1",
        "name": "Advanced",
        "min_score": 8.5,
        "max_score": 9.3,
        "difficulty_mapping": "hard",
        "description": "Can express ideas fluently and spontaneously without much obvious searching for expressions.",
    },
    {
        "code": "C2",
        "name": "Proficient",
        "min_score": 9.3,
        "max_score": 10.0,
        "difficulty_mapping": "hard",
        "description": "Can understand with ease virtually everything heard or read and summarize information coherently.",
    },
]


def score_to_cefr(score: Optional[float]) -> Dict:
    """Map a 0-10 score to a standard CEFR band."""
    if score is None:
        return {
            "cefr_level": "B1",
            "cefr_name": "Intermediate",
            "recommended_difficulty": "medium",
            "description": "Initial baseline placement.",
        }

    clamped = max(0.0, min(10.0, float(score)))

    for level in reversed(CEFR_LEVELS):
        if clamped >= level["min_score"]:
            return {
                "cefr_level": level["code"],
                "cefr_name": level["name"],
                "recommended_difficulty": level["difficulty_mapping"],
                "description": level["description"],
                "normalized_score": round(clamped, 1),
            }

    # Fallback to A1
    return {
        "cefr_level": "A1",
        "cefr_name": "Beginner",
        "recommended_difficulty": "easy",
        "description": CEFR_LEVELS[0]["description"],
        "normalized_score": round(clamped, 1),
    }


def calculate_adaptive_difficulty(
    recent_overall_scores: List[float],
    current_difficulty: str = "medium",
) -> Dict:
    """Calculate moving-average proficiency and determine if learner should adjust difficulty.

    Does not force difficulty changes; provides recommendation and adaptive guidance.
    """
    valid_scores = [float(s) for s in recent_overall_scores if s is not None and 0.0 <= float(s) <= 10.0]

    if not valid_scores:
        cefr = score_to_cefr(None)
        return {
            "adaptive_difficulty": current_difficulty,
            "recommended_difficulty": current_difficulty,
            "cefr_level": cefr["cefr_level"],
            "cefr_name": cefr["cefr_name"],
            "moving_average": None,
            "sample_size": 0,
            "progression_trend": "Insufficient data (first session)",
        }

    # Exponentially weighted recent performance
    weights = [1.2 ** i for i in range(len(valid_scores))]
    total_weight = sum(weights)
    weighted_avg = round(sum(s * w for s, w in zip(valid_scores, weights)) / total_weight, 1)

    cefr = score_to_cefr(weighted_avg)
    recommended = cefr["recommended_difficulty"]

    # Trend calculation
    if len(valid_scores) >= 3:
        first_half = sum(valid_scores[: len(valid_scores) // 2]) / (len(valid_scores) // 2)
        second_half = sum(valid_scores[len(valid_scores) // 2 :]) / (len(valid_scores) - len(valid_scores) // 2)
        diff = second_half - first_half
        if diff >= 0.8:
            trend = "Accelerating improvement"
        elif diff <= -0.8:
            trend = "Experiencing difficulty; needs consolidation"
        else:
            trend = "Consistent steady performance"
    else:
        trend = "Building baseline profile"

    return {
        "adaptive_difficulty": recommended,
        "recommended_difficulty": recommended,
        "cefr_level": cefr["cefr_level"],
        "cefr_name": cefr["cefr_name"],
        "moving_average": weighted_avg,
        "sample_size": len(valid_scores),
        "progression_trend": trend,
    }
