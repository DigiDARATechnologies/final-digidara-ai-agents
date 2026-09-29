"""Unit tests verifying production enhancements for Communication Coach Agent.

Tests:
1. Phonetic analysis and approximate IPA generation
2. Phoneme deviation detection and articulatory guidance
3. Speech rate and prosody metric computation
4. Non-breaking extensions to assess_pronunciation
5. Adaptive CEFR calibration and moving-average progression
6. Thread-safe LRU caching for phonetic hints and grammar checks
"""

import pytest

from app.services.cache_service import get_cached, set_cached
from app.services.cefr_adaptation import calculate_adaptive_difficulty, score_to_cefr
from app.services.phonetic_analysis import (
    analyze_phonetic_deviations,
    approximate_word_ipa,
    compute_prosody_metrics,
)
from app.services.pronunciation_assessment import assess_pronunciation


def test_approximate_word_ipa():
    ipa = approximate_word_ipa("think")
    assert "/θ" in ipa
    ipa_ship = approximate_word_ipa("ship")
    assert "/ʃ" in ipa_ship


def test_phonetic_deviations_detection():
    diffs = [{"expected": "think", "recognised": "sink"}]
    deviations = analyze_phonetic_deviations(["think"], ["sink"], diffs)
    assert len(deviations) == 1
    assert deviations[0]["target_word"] == "think"
    assert deviations[0]["issue_category"] == "th sound"
    assert "teeth" in deviations[0]["articulatory_guidance"]


def test_compute_prosody_metrics():
    # 30 words in 12 seconds = 150 WPM (Natural pace)
    text = "word " * 30
    prosody = compute_prosody_metrics(text, text, duration_seconds=12.0, recognition_confidence=0.92)
    assert prosody["wpm"] == 150.0
    assert prosody["tempo_rating"] == "Natural Pace"
    assert prosody["tempo_score"] >= 9.0


def test_assess_pronunciation_backward_compatibility():
    expected = "Good morning everyone"
    recognised = "Good morning everyone"
    res = assess_pronunciation(expected, recognised, recognition_confidence=0.95, duration_seconds=2.0)

    # Core existing schema keys must be present and valid
    assert res["exact_match"] is True
    assert res["match_percentage"] >= 95
    assert "word_accuracy" in res["scores"]
    assert "completeness" in res["scores"]
    assert "clarity" in res["scores"]
    assert "fluency" in res["scores"]
    assert "overall" in res["scores"]

    # New non-breaking diagnostic keys must also be populated
    assert "phonetic_deviations" in res
    assert "prosody_metrics" in res
    assert "target_ipa" in res
    assert "recognised_ipa" in res
    assert res["prosody_metrics"]["wpm"] is not None


def test_cefr_score_mapping():
    beginner = score_to_cefr(3.5)
    assert beginner["cefr_level"] == "A1"
    assert beginner["recommended_difficulty"] == "easy"

    intermediate = score_to_cefr(7.0)
    assert intermediate["cefr_level"] == "B1"
    assert intermediate["recommended_difficulty"] == "medium"

    advanced = score_to_cefr(9.5)
    assert advanced["cefr_level"] == "C2"
    assert advanced["recommended_difficulty"] == "hard"


def test_adaptive_difficulty_progression():
    # Rolling scores trending strongly upward into advanced level
    scores = [7.5, 8.5, 9.0, 9.2, 9.6]
    result = calculate_adaptive_difficulty(scores, current_difficulty="medium")
    assert result["recommended_difficulty"] == "hard"
    assert result["cefr_level"] in {"C1", "C2"}
    assert "improvement" in result["progression_trend"]


def test_cache_service_lru():
    set_cached("test_ns", {"score": 9.5}, ttl_seconds=60, word="test")
    hit = get_cached("test_ns", word="test")
    assert hit is not None
    assert hit["score"] == 9.5

    miss = get_cached("test_ns", word="different")
    assert miss is None
