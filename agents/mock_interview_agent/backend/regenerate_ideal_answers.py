"""Regenerate stored interview-recommended answers with the current OpenAI prompt."""

import argparse
import logging

from dotenv import load_dotenv

load_dotenv()

import db
from structured_logging import configure_root_structured_logging, log_event


configure_root_structured_logging()
logger = logging.getLogger(__name__)


def report(event, message, level=logging.INFO, *, exc_info=False):
    log_event(logger, level, event, message, exc_info=exc_info)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate interview_details.ideal_answer values. The default is "
            "a read-only preview; pass --apply to call OpenAI and save changes."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Call OpenAI and update matching database rows.",
    )
    parser.add_argument(
        "--interview-id",
        type=int,
        help="Limit regeneration to one interview ID.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only process rows whose ideal_answer is empty.",
    )
    return parser.parse_args()


def load_rows(interview_id=None, only_missing=False):
    conditions = ["d.verdict IS NOT NULL"]
    params = []
    if interview_id is not None:
        conditions.append("d.interview_id = %s")
        params.append(interview_id)
    if only_missing:
        conditions.append(
            "(d.ideal_answer IS NULL OR TRIM(d.ideal_answer) = '')"
        )

    where_clause = " AND ".join(conditions)
    rows, _ = db.query(
        f"""SELECT d.id, d.interview_id, d.question, i.difficulty, i.round_type
            FROM interview_details d
            JOIN interviews i ON i.id = d.interview_id
            WHERE {where_clause}
            ORDER BY d.interview_id, d.question_order, d.id""",
        tuple(params),
        fetch=True,
    )
    return rows


def main():
    args = parse_args()
    rows = load_rows(args.interview_id, args.only_missing)
    report("ideal_answer_rows_matched", f"Matched {len(rows)} evaluated question rows")

    if not args.apply:
        report("ideal_answer_preview", "Preview only; no OpenAI calls or database updates were made")
        report("ideal_answer_preview_instruction", "Run again with --apply to regenerate and save answers")
        return

    import groq_client

    updated = 0
    failed = 0
    for row in rows:
        try:
            ideal_answer = groq_client.generate_ideal_answer(
                row["question"],
                row["difficulty"],
                row["round_type"],
            )
            db.query(
                "UPDATE interview_details SET ideal_answer = %s WHERE id = %s",
                (ideal_answer, row["id"]),
            )
            updated += 1
            report(
                "ideal_answer_updated",
                f"Updated detail {row['id']} "
                f"(interview {row['interview_id']})."
            )
        except Exception as exc:
            failed += 1
            report(
                "ideal_answer_update_failed",
                f"Failed to update detail {row['id']}: {exc}",
                logging.ERROR,
                exc_info=True,
            )

    report(
        "ideal_answer_regeneration_completed",
        f"Finished: {updated} updated, {failed} failed",
        logging.ERROR if failed else logging.INFO,
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
