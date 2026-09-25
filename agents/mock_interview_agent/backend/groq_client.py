"""Compatibility facade for the interview AI modules.

The legacy module name is retained so routes and maintenance scripts keep
their existing imports while all provider calls use OpenAI internally.
"""

import random

from ai.answer_evaluation import (
    IDEAL_ANSWER_MAX_WORDS,
    evaluate_answer as _evaluate_answer,
    evaluate_interview as _evaluate_interview,
    evaluate_answers_batch as _evaluate_answers_batch,
    generate_ideal_answer as _generate_ideal_answer,
)
from ai.chat_client import (
    OPENAI_REQUEST_TIMEOUT_SECONDS,
    MODEL,
    EVAL_MODEL,
    TRANSCRIPTION_MODEL,
    TRANSCRIPTION_PROMPTS,
    build_transcription_prompt,
    chat as _chat,
    client,
    json_object as _json_object,
    score as _score,
    transcribe_audio,
)
from ai.question_generation import (
    GENERIC_SUBTOPIC_HINTS,
    HR_QUESTION_AREAS,
    PRESET_SUBJECTS,
    PRESET_ROLE_SKILLS,
    CUSTOM_FALLBACK_TOPIC_AREAS,
    infer_role_skills as _infer_role_skills,
    generate_question as _generate_question,
    build_interview_questions as _build_interview_questions,
)
from ai.validators import (
    QUESTION_COMPLEXITY_PATTERN,
    QUESTION_GENERATION_MAX_ATTEMPTS,
    QUESTION_INTERROGATIVE_PATTERN,
    QUESTION_WORD_LIMITS,
    QUESTION_WORD_PATTERN,
    SAFE_HR_QUESTION_TEMPLATES,
    SAFE_QUESTION_TEMPLATES,
    _question_validation_errors,
    _safe_fallback_question,
    _normalized_topic_area,
    _question_payload,
    _validated_question_payload_with_retries,
)
from services.role_interviews import resolve_role_subjects as _resolve_role_subjects


def generate_question(
    round_type, subject, difficulty, asked_so_far, recent_topic_areas=None,
    role_context=None, already_asked_hashes=None, already_asked_questions=None,
    role_skills=None, skill_area=None,
):
    return _generate_question(
        round_type,
        subject,
        difficulty,
        asked_so_far,
        recent_topic_areas,
        role_context,
        already_asked_hashes,
        already_asked_questions,
        role_skills,
        skill_area,
        chat_fn=_chat,
        rng=random,
    )


def resolve_role_subjects(role):
    return _resolve_role_subjects(role, chat_fn=_chat)


def infer_role_skills(role_or_topic, difficulty):
    return _infer_role_skills(role_or_topic, difficulty, chat_fn=_chat)


def build_interview_questions(
    role, difficulty, round_type, total_count, generate_ai_question,
    already_asked_hashes=None, role_skills=None, initial_asked_context=None,
    skill_order=None,
):
    return _build_interview_questions(
        role, difficulty, round_type, total_count,
        chat_fn=_chat, generate_ai_question=generate_ai_question, rng=random,
        already_asked_hashes=already_asked_hashes,
        role_skills=role_skills,
        initial_asked_context=initial_asked_context,
        skill_order=skill_order,
    )


def evaluate_answer(question, answer, difficulty, round_type="technical"):
    return _evaluate_answer(
        question,
        answer,
        difficulty,
        round_type,
        chat_fn=_evaluation_chat,
    )


def generate_ideal_answer(question, difficulty, round_type="technical"):
    return _generate_ideal_answer(
        question,
        difficulty,
        round_type,
        chat_fn=_chat,
    )


def evaluate_interview(round_type, subject, difficulty, qa_pairs):
    return _evaluate_interview(
        round_type,
        subject,
        difficulty,
        qa_pairs,
        chat_fn=_evaluation_chat,
    )


def evaluate_answers_batch(round_type, subject, difficulty, qa_pairs):
    return _evaluate_answers_batch(round_type, subject, difficulty, qa_pairs, chat_fn=_evaluation_chat)




def _evaluation_chat(messages, json_mode=False, temperature=0.7, **kwargs):
    """Route scoring calls to the independently configurable evaluator model."""
    return _chat(
        messages,
        json_mode=json_mode,
        temperature=temperature,
        model_override=EVAL_MODEL,
        **kwargs,
    )
