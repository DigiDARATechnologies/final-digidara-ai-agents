"""Print token usage for one interview.

Run from this directory with:
    python check_interview_tokens.py <interview_id>
"""

from pathlib import Path
import sys

# Allow the script to be run directly from backend/scripts without installing
# the backend as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db


PURPOSES = (
    ("Question generation", ("initial_question_generation", "next_question_generation", "followup_generation")),
    ("Answer evaluation", ("answer_evaluation", "answer_evaluation_batch")),
    ("Scorecard", ("final_interview_evaluation",)),
    ("Transcription", ("audio_transcription",)),
    ("Web search", ("web_search", "live_question_search")),
)


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit("Usage: python check_interview_tokens.py <interview_id>")
    interview_id = int(sys.argv[1])

    interview, _ = db.query(
        "SELECT id, status FROM interviews WHERE id = %s",
        (interview_id,), fetchone=True,
    )
    if not interview:
        raise SystemExit(f"Interview {interview_id} was not found.")

    rows, _ = db.query(
        """SELECT request_type, COUNT(*) AS calls,
                  COALESCE(SUM(prompt_tokens), 0) AS input_tokens,
                  COALESCE(SUM(completion_tokens), 0) AS output_tokens,
                  COALESCE(SUM(total_tokens), 0) AS total_tokens
           FROM ai_usage_records
           WHERE interview_id = %s
           GROUP BY request_type""",
        (interview_id,), fetch=True,
    )
    by_type = {row["request_type"]: row for row in rows}

    print(f"Interview {interview_id} (status: {interview['status']})")
    print("-" * 78)
    print(f"{'Purpose':<24} {'Calls':>7} {'Input':>12} {'Output':>12} {'Total':>12}")
    print("-" * 78)
    grand_total = 0
    for label, request_types in PURPOSES:
        matching = [by_type[name] for name in request_types if name in by_type]
        calls = sum(int(row["calls"] or 0) for row in matching)
        input_tokens = sum(int(row["input_tokens"] or 0) for row in matching)
        output_tokens = sum(int(row["output_tokens"] or 0) for row in matching)
        total_tokens = sum(int(row["total_tokens"] or 0) for row in matching)
        grand_total += total_tokens
        print(f"{label:<24} {calls:>7} {input_tokens:>12,} {output_tokens:>12,} {total_tokens:>12,}")
    print("-" * 78)
    print(f"{'TOTAL':<24} {'':>7} {'':>12} {'':>12} {grand_total:>12,}")


if __name__ == "__main__":
    main()
