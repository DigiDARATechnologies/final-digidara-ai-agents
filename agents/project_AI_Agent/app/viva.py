"""Post-grading viva (oral defense) layer.

Deliberately NOT part of the LangGraph submission_graph -- that graph is
single-shot and non-checkpointed by design (see graph.py's module
docstring: resumable submission graphs previously caused a class of replay
bugs). The viva is its own small, simple back-and-forth that reads/writes
columns on the Submission row directly, one question at a time, instead of
trying to make the graph itself resumable again.
"""
from __future__ import annotations

from app.graph import prompts
from app.llm.client import call_json

VIVA_QUESTION_COUNT = 10
VIVA_PASS_THRESHOLD = 6


def generate_viva_questions(chosen_topic: dict, course_medium: str, code_files: dict) -> list[dict]:
    result = call_json(
        system=prompts.viva_question_generator_prompt(chosen_topic, course_medium, code_files),
        user="Generate the 10 viva questions now.",
        temperature=0.7,
    )
    questions = result.get("questions", [])[:VIVA_QUESTION_COUNT]
    return [
        {"id": i, "question": q.get("question", ""), "expected_concepts": q.get("expected_concepts", [])}
        for i, q in enumerate(questions)
    ]


def verify_viva_answer(question: str, expected_concepts: list, answer: str) -> dict:
    result = call_json(
        system=prompts.viva_answer_verifier_prompt(question, expected_concepts, answer),
        user="Grade this answer now.",
        temperature=0.2,
    )
    return {"correct": bool(result.get("correct", False)), "note": result.get("note", "")}
