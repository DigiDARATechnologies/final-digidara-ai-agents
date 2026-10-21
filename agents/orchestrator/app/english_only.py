"""Every DigiDARA agent works in English only.

Typed input written in another script -- Tamil, Hindi, Telugu, Malayalam,
Kannada, Arabic, Chinese and so on -- is refused with one friendly message,
before it reaches an agent or a language model. Only scripts are checked: plain
Latin letters, digits, punctuation, emoji, accented letters (résumé) and math
symbols (π, Σ, √) are always accepted.

Speech is already written as English by every microphone (the transcription
calls pass language="en"), and the voice always speaks English.
"""
from __future__ import annotations

ENGLISH_ONLY_MESSAGE = "Please type in English. DigiDARA agents understand and reply in English only."

# Unicode blocks of scripts that are not English.
_OTHER_SCRIPTS = (
    (0x0400, 0x052F),  # Cyrillic
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x08FF),  # Syriac, Thaana, Arabic supplements
    (0x0900, 0x0DFF),  # Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, Sinhala
    (0x0E00, 0x0FFF),  # Thai, Lao, Tibetan
    (0x1000, 0x109F),  # Myanmar
    (0x10A0, 0x10FF),  # Georgian
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x1780, 0x17FF),  # Khmer
    (0x3040, 0x30FF),  # Hiragana, Katakana
    (0x3130, 0x318F),  # Hangul compatibility Jamo
    (0x3400, 0x4DBF),  # CJK extension A
    (0x4E00, 0x9FFF),  # CJK
    (0xA8E0, 0xA8FF),  # Devanagari extended
    (0xAC00, 0xD7AF),  # Hangul syllables
    (0xFB1D, 0xFDFF),  # Hebrew and Arabic presentation forms
    (0xFE70, 0xFEFF),  # Arabic presentation forms B
    (0x11FC0, 0x11FFF),  # Tamil supplement
)

# Fields that hold program code or its input: a print("வணக்கம்") in a
# coding exercise is code, not the learner talking in Tamil.
_SKIPPED_KEYS = frozenset({"code", "source_code", "sourcecode", "stdin", "starter_code", "solution"})


def _is_other_script(ch: str) -> bool:
    point = ord(ch)
    return any(low <= point <= high for low, high in _OTHER_SCRIPTS)


def is_english_text(text: str) -> bool:
    """False when the text contains letters of a non-English script."""
    return not any(_is_other_script(ch) for ch in text or "")


def require_english(*texts: str | None) -> None:
    """HTTP 400 with the English-only message when any text is in another script."""
    if any(text and not is_english_text(text) for text in texts):
        from fastapi import HTTPException

        raise HTTPException(400, ENGLISH_ONLY_MESSAGE)


def contains_non_english(value, _depth: int = 0) -> bool:
    """True when any string in a JSON-like value (skipping code fields) is
    written in a non-English script."""
    if _depth > 20:
        return False
    if isinstance(value, str):
        return not is_english_text(value)
    if isinstance(value, dict):
        return any(
            contains_non_english(item, _depth + 1)
            for key, item in value.items()
            if str(key).lower() not in _SKIPPED_KEYS
        )
    if isinstance(value, (list, tuple)):
        return any(contains_non_english(item, _depth + 1) for item in value)
    return False
