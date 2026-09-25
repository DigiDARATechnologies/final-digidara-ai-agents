"""Post-grading viva (oral defense) layer.

Deliberately NOT part of the LangGraph submission_graph -- that graph is
single-shot and non-checkpointed by design (see graph.py's module
docstring: resumable submission graphs previously caused a class of replay
bugs). The viva is its own small, simple back-and-forth that reads/writes
columns on the Submission row directly, one question at a time, instead of
trying to make the graph itself resumable again.

A student gets VIVA_ATTEMPTS attempts. Every attempt asks a fresh set of
questions (never one already asked in an earlier attempt), needs at least
VIVA_PASS_PERCENT of the answers correct, and is reported to the student as
Good / Average / Bad rather than as a mark.
"""
from __future__ import annotations

import re

from app.graph import prompts
from app.llm.client import call_json

VIVA_QUESTION_COUNT = 10
VIVA_ATTEMPTS = 3
VIVA_PASS_PERCENT = 50
# Kept for callers that show the pass mark as a count of correct answers.
VIVA_PASS_THRESHOLD = VIVA_QUESTION_COUNT * VIVA_PASS_PERCENT // 100
VIVA_GOOD_PERCENT = 80
# Extra generation rounds allowed to replace questions that repeat an earlier one.
_TOP_UP_ROUNDS = 3


def viva_passed(correct: int, total: int) -> bool:
    return total > 0 and correct * 100 >= VIVA_PASS_PERCENT * total


def viva_rating(correct: int, total: int) -> str:
    """Good / Average / Bad -- the only way a viva result is shown to the student."""
    if total <= 0:
        return "Bad"
    percent = correct * 100 / total
    if percent >= VIVA_GOOD_PERCENT:
        return "Good"
    return "Average" if percent >= VIVA_PASS_PERCENT else "Bad"


def _fingerprint(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(question).lower()).strip()


def generate_viva_questions(chosen_topic: dict, course_medium: str, code_files: dict, avoid: list[str] | None = None) -> list[dict]:
    """Up to VIVA_QUESTION_COUNT questions, none of them repeating one in `avoid`
    (the questions of earlier attempts) or each other. The model is asked to vary,
    but repetition is checked here in code and topped up rather than trusted."""
    seen = {_fingerprint(question) for question in (avoid or [])}
    avoid_list = [str(question) for question in (avoid or [])]
    chosen: list[dict] = []
    for _ in range(1 + _TOP_UP_ROUNDS):
        result = call_json(
            system=prompts.viva_question_generator_prompt(chosen_topic, course_medium, code_files, avoid_list or None),
            user="Generate the 10 viva questions now.",
            temperature=0.7,
        )
        for item in result.get("questions", []):
            text = str(item.get("question", "")).strip()
            key = _fingerprint(text)
            if not key or key in seen:
                continue
            seen.add(key)
            avoid_list.append(text)
            chosen.append({"question": text, "expected_concepts": item.get("expected_concepts", [])})
        if len(chosen) >= VIVA_QUESTION_COUNT:
            break
    return [{"id": i, **item} for i, item in enumerate(chosen[:VIVA_QUESTION_COUNT])]


def verify_viva_answer(question: str, expected_concepts: list, answer: str) -> dict:
    result = call_json(
        system=prompts.viva_answer_verifier_prompt(question, expected_concepts, answer),
        user="Grade this answer now.",
        temperature=0.2,
    )
    return {"correct": bool(result.get("correct", False)), "note": result.get("note", "")}
