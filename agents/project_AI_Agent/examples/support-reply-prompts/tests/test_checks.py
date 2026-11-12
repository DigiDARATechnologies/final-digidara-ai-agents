import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checks import check_response  # noqa: E402
from evaluate import load_cases, score_version  # noqa: E402

NO_REFUND = {"expected_category": "refund_request", "refund_allowed": False}
GOOD = json.dumps({"category": "refund_request",
                   "reply": "Hi, our return window is 30 days, so we can't take it back. - Nila Home Support"})


def test_a_good_reply_passes_every_check():
    assert all(check_response(GOOD, NO_REFUND).values())


def test_text_around_the_json_is_not_valid_json():
    result = check_response("Here is the reply:\n" + GOOD, NO_REFUND)
    assert result["valid_json"] is False
    assert result["category"] is False


def test_a_refund_the_policy_does_not_allow_is_caught():
    raw = json.dumps({"category": "refund_request", "reply": "Hi, we will refund you. - Nila Home Support"})
    assert check_response(raw, NO_REFUND)["refund_safe"] is False


def test_a_refund_is_fine_when_the_policy_allows_it():
    raw = json.dumps({"category": "payment_issue", "reply": "Hi, the duplicate will be refunded. - Nila Home Support"})
    assert check_response(raw, {"expected_category": "payment_issue", "refund_allowed": True})["refund_safe"] is True


def test_a_reply_over_120_words_fails_length():
    raw = json.dumps({"category": "refund_request", "reply": "Hi, " + "word " * 130 + "- Nila Home Support"})
    assert check_response(raw, NO_REFUND)["length"] is False


def test_the_final_prompt_beats_the_baseline():
    cases = load_cases()
    baseline, _ = score_version("v1_baseline", cases)
    final, _ = score_version("v3_few_shot_json", cases)
    assert sum(final.values()) > sum(baseline.values())
