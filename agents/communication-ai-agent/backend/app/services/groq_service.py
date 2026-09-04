"""Compatibility facade for Groq-backed AI services.

Routes still import this module, while implementation lives in smaller
domain modules. This keeps the public API stable during the refactor.
"""

from .groq_common import (
    fallback_practice_topic,
    fallback_practice_topics,
    generate_practice_topic,
    generate_practice_topics,
    generate_speaking_topics,
)
from .groq_pronunciation import (
    generate_pronunciation_feedback,
    generate_pronunciation_item,
    summarize_pronunciation_session,
)
from .groq_speaking import (
    GroqRateLimitError,
    evaluate_daily_answer,
    evaluate_speaking_answer,
    fallback_speaking_question,
    fallback_daily_conversation_set,
    generate_daily_conversation_set,
    generate_speaking_question,
    repair_speaking_correction,
    strip_completion_command,
    summarize_speaking_session,
    transcribe_speaking_audio,
)
from .groq_writing import (
    detect_tone,
    evaluate_sentence_rewrite,
    evaluate_writing_answer,
    generate_sentence_rewrite_prompt,
    generate_writing_hint,
    generate_writing_prompt,
    live_writing_check,
    live_writing_insights,
    quick_grammar_check,
    summarize_writing_session,
)

__all__ = [
    "detect_tone",
    "GroqRateLimitError",
    "evaluate_daily_answer",
    "evaluate_sentence_rewrite",
    "evaluate_speaking_answer",
    "evaluate_writing_answer",
    "fallback_practice_topic",
    "fallback_practice_topics",
    "fallback_daily_conversation_set",
    "fallback_speaking_question",
    "generate_daily_conversation_set",
    "generate_practice_topic",
    "generate_practice_topics",
    "generate_pronunciation_feedback",
    "generate_pronunciation_item",
    "generate_sentence_rewrite_prompt",
    "generate_speaking_question",
    "generate_speaking_topics",
    "generate_writing_hint",
    "generate_writing_prompt",
    "live_writing_check",
    "live_writing_insights",
    "quick_grammar_check",
    "repair_speaking_correction",
    "summarize_pronunciation_session",
    "summarize_speaking_session",
    "strip_completion_command",
    "summarize_writing_session",
    "transcribe_speaking_audio",
]
