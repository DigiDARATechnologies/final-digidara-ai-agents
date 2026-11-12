"""Rule-based checks for one model response. No API calls, so the scores are repeatable."""
import json
import re

CATEGORIES = {
    "damaged_item", "delivery_status", "refund_request", "exchange",
    "payment_issue", "complaint", "product_question", "cancellation",
}
MAX_WORDS = 120
SIGN_OFF = "- Nila Home Support"
CHECK_NAMES = ["valid_json", "category", "refund_safe", "length", "format"]


def parse(raw):
    """The response as {"category", "reply"}, or None if it is not exactly that JSON object."""
    try:
        data = json.loads(raw.strip())
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("reply"), str) or data.get("category") not in CATEGORIES:
        return None
    return data


def check_response(raw, case):
    """Return {check_name: passed} for one response to one test case."""
    data = parse(raw)
    reply = data["reply"] if data else raw
    return {
        # The app reads the category and reply from JSON, so anything else is unusable.
        "valid_json": data is not None,
        "category": bool(data) and data["category"] == case["expected_category"],
        # Mentioning a refund the policy doesn't allow sets a false expectation.
        "refund_safe": case["refund_allowed"] or not re.search(r"\brefund", reply, re.IGNORECASE),
        "length": len(reply.split()) <= MAX_WORDS,
        "format": reply.startswith("Hi,") and reply.rstrip().endswith(SIGN_OFF),
    }
