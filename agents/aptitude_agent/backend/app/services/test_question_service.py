"""Batch question preparation and persisted difficulty reporting."""

import time
import uuid

from flask import current_app

from ..extensions import db
from ..models import AptitudeTestQuestion, RecentQuestionHash
from .audit_service import record_event
from .question_timing import question_time_seconds
from .test_generation import generate_questions
from .usage_service import record_usage


DIFFICULTIES = ("Easy", "Medium", "Hard")
DIFFICULTY_LEVEL = {"Easy": 1, "Medium": 2, "Hard": 3}


def _recent_question_texts(student_id):
    rows = (
        RecentQuestionHash.query.filter_by(student_id=student_id)
        .order_by(RecentQuestionHash.created_at.desc())
        .limit(current_app.config["RECENT_QUESTION_HISTORY_LIMIT"])
        .all()
    )
    hashes = {row.content_hash for row in rows}
    if not hashes:
        return []
    return [
        row.question_text
        for row in (
            AptitudeTestQuestion.query.filter(AptitudeTestQuestion.content_hash.in_(hashes))
            .order_by(AptitudeTestQuestion.generated_at.desc())
            .limit(60)
            .all()
        )
    ]


def generate_and_store_question_batch(test, slots):
    """Generate, validate, and stage a complete test in one provider request.

    The caller owns the transaction. No question is committed until every
    generated item and its audit/usage records have been staged successfully.
    Validation retries inside ``generate_questions`` are bounded recovery;
    the successful path performs one provider request for the complete batch.
    """
    if len(slots) != test.total_questions:
        raise ValueError("Question blueprint does not match the test question count")

    started = time.perf_counter()
    deadline = time.monotonic() + current_app.config["BATCH_GENERATION_DEADLINE_SECONDS"]
    try:
        generated, model, usage = generate_questions(
            slots,
            avoid_questions=_recent_question_texts(test.student_id),
            allow_demo_fallback=current_app.config["ALLOW_DEMO_QUESTIONS"],
            deadline=deadline,
            max_validation_attempts=current_app.config["BATCH_GENERATION_MAX_ATTEMPTS"],
            request_timeout=current_app.config["OPENAI_BATCH_TIMEOUT_SECONDS"],
        )
        if len(generated) != len(slots):
            raise ValueError(f"Expected {len(slots)} generated questions")

        questions = []
        fixed_reason = (
            "fixed mixed-test difficulty distribution"
            if test.test_mode == "mixed"
            else "fixed category-practice difficulty"
        )
        for sequence, item in enumerate(generated, start=1):
            question = AptitudeTestQuestion(
                id=str(uuid.uuid4()),
                test_id=test.id,
                sequence_no=sequence,
                category=item["category"],
                topic=item["topic"],
                difficulty=item["difficulty"],
                difficulty_reason=fixed_reason,
                question_text=item["question"],
                option_a=item["options"]["A"],
                option_b=item["options"]["B"],
                option_c=item["options"]["C"],
                option_d=item["options"]["D"],
                correct_answer=item["correct_answer"],
                explanation=item["explanation"],
                allowed_time_seconds=question_time_seconds(item["difficulty"]),
                generation_model=model,
                hint_text=None,
                prompt_version="batch-v1",
                content_hash=item["content_hash"],
                structural_hash=item["structural_hash"],
                source_bank_item_id=None,
            )
            questions.append(question)
            db.session.add(question)
            db.session.add(
                RecentQuestionHash(
                    student_id=test.student_id,
                    test_id=test.id,
                    category=question.category,
                    topic=question.topic,
                    content_hash=question.content_hash,
                    structural_hash=question.structural_hash,
                    bank_question_id=None,
                )
            )

        # A single usage row represents the single batch call accurately.
        record_usage(test.student_id, "question_batch_generation", model, usage, test.id)
        record_event(
            "question_batch_generated",
            test.student_id,
            test.id,
            {
                "mode": test.test_mode,
                "question_count": len(questions),
                "model": model,
                "prompt_tokens": int(usage.get("input_tokens", 0) or 0),
                "completion_tokens": int(usage.get("output_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
                "provider_attempts": int(usage.get("provider_attempt_count", 0) or 0),
                "validation_attempts": int(usage.get("validation_attempt_count", 1) or 1),
                "finish_reason": usage.get("finish_reason"),
                "response_truncated": bool(usage.get("response_truncated", False)),
            },
        )
        db.session.flush()
        current_app.logger.info(
            "Question batch test_id=%s test_type=%s operation=question_batch_generation "
            "model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "provider_attempts=%s validation_attempts=%s finish_reason=%s response_truncated=%s status=success questions=%s duration_ms=%.2f",
            test.id,
            test.test_mode,
            model,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            usage.get("total_tokens", 0),
            usage.get("provider_attempt_count", 0),
            usage.get("validation_attempt_count", 1),
            usage.get("finish_reason"),
            usage.get("response_truncated", False),
            len(questions),
            (time.perf_counter() - started) * 1000,
        )
        return questions, model, usage
    except Exception as exc:
        current_app.logger.warning(
            "Question batch test_id=%s test_type=%s operation=question_batch_generation "
            "status=failed error_type=%s error=%s duration_ms=%.2f",
            test.id,
            test.test_mode,
            type(exc).__name__,
            str(exc)[:300],
            (time.perf_counter() - started) * 1000,
        )
        raise


def _average_label(value):
    if value < 1.5:
        return "Easy"
    if value < 2.5:
        return "Medium"
    return "Hard"


def difficulty_metrics(test):
    """Summarize persisted fixed difficulties for result compatibility."""
    by_category = {}
    for question in test.questions:
        by_category.setdefault(question.category, []).append(question)
    categories = []
    for category, questions in by_category.items():
        levels = [DIFFICULTY_LEVEL[question.difficulty] for question in questions]
        average = sum(levels) / len(levels)
        peak = max(questions, key=lambda question: DIFFICULTY_LEVEL[question.difficulty]).difficulty
        answered = [question for question in questions if question.answer]
        correct = sum(int(question.answer.is_correct) for question in answered)
        categories.append(
            {
                "category": category,
                "questions": len(questions),
                "accuracy": round(correct / len(answered) * 100, 1) if answered else 0,
                "average_level": round(average, 2),
                "average_difficulty": _average_label(average),
                "peak_difficulty": peak,
            }
        )
    all_levels = [DIFFICULTY_LEVEL[question.difficulty] for question in test.questions]
    if not all_levels:
        return {
            "average_difficulty": None,
            "average_level": 0,
            "peak_difficulty": None,
            "peak_categories": [],
            "difficulty_by_category": [],
        }
    overall = sum(all_levels) / len(all_levels)
    peak = DIFFICULTIES[max(all_levels) - 1]
    return {
        "average_difficulty": _average_label(overall),
        "average_level": round(overall, 2),
        "peak_difficulty": peak,
        "peak_categories": [row["category"] for row in categories if row["peak_difficulty"] == peak],
        "difficulty_by_category": categories,
    }
