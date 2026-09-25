"""Generate six real question sets for manual difficulty-calibration review.

Run inside the configured backend container. This calls the live provider and
does not create interviews or write to the application database.
"""

import argparse
import json
import random
import time
from pathlib import Path

import groq_client
from ai import question_generation
from ai.validators import _beginner_technical_question_errors


def _provider_questions(replies):
    questions = set()
    for raw in replies:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            continue
        items = value.get("questions", []) if isinstance(value, dict) else []
        if isinstance(value, dict) and isinstance(value.get("question"), str):
            items = [value]
        for item in items:
            if isinstance(item, dict):
                questions.add(" ".join(str(item.get("question", "")).split()))
    return questions


def generate_six_sets(role):
    runs = []
    for round_type in ("technical", "hr"):
        for difficulty in ("beginner", "intermediate", "advanced"):
            started = time.monotonic()
            replies = []

            def capture_chat(messages, **kwargs):
                response = groq_client._chat(messages, **kwargs)
                replies.append(response)
                return response

            if round_type == "technical":
                skills = groq_client.infer_role_skills(role, difficulty)
                plan = question_generation.build_interview_questions(
                    role, difficulty, "technical", 10,
                    chat_fn=capture_chat,
                    generate_ai_question=lambda *_args: None,
                    rng=random.Random(42),
                    role_skills=skills,
                )
            else:
                plan, asked, areas = [], [], []
                for _ in range(10):
                    item = question_generation.generate_question(
                        "hr", None, difficulty, asked,
                        recent_topic_areas=areas,
                        chat_fn=capture_chat,
                        rng=random.Random(42),
                    )
                    plan.append(item)
                    asked.append(item["question"])
                    areas.append(item["topic_area"])

            questions = [{
                "number": index,
                "topic_area": item["topic_area"],
                "question": item["question"],
            } for index, item in enumerate(plan, 1)]
            provider_questions = _provider_questions(replies)
            run = {
                "round": round_type,
                "difficulty": difficulty,
                "role": role if round_type == "technical" else None,
                "questions": questions,
                "provider_responses": len(replies),
                "fallback_count": sum(
                    item["question"] not in provider_questions for item in questions
                ),
                "beginner_exclusion_flags": [
                    item["number"] for item in questions
                    if round_type == "technical" and difficulty == "beginner"
                    and _beginner_technical_question_errors(item["question"])
                ],
                "elapsed_seconds": round(time.monotonic() - started, 1),
            }
            runs.append(run)
            print(
                "SET_DONE", round_type, difficulty,
                "count", len(questions),
                "provider_responses", run["provider_responses"],
                "fallbacks", run["fallback_count"],
                "flags", run["beginner_exclusion_flags"],
                flush=True,
            )
    return runs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="Python Fullstack Developer")
    parser.add_argument("--output", default="/tmp/mock_difficulty_live_six_sets.json")
    args = parser.parse_args()
    result = generate_six_sets(args.role)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print("ALL_DONE", len(result), args.output, flush=True)
