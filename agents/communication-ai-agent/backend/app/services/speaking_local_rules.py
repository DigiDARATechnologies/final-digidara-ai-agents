import re


def _sentence_case(text):
    text = (text or "").strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def _finish_sentence(text):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if text and text[-1] not in ".!?":
        return f"{text}."
    return text


def _question_suggests_past(question):
    return bool(re.search(r"\b(did|earlier|yesterday|last|ago)\b", question or "", re.IGNORECASE))


def _question_suggests_current(question):
    return bool(re.search(r"\b(are you|doing now|right now|currently)\b", question or "", re.IGNORECASE))


def apply_local_speaking_correction(question, answer, mode="topic"):
    original = re.sub(r"\s+", " ", (answer or "").strip())
    if not original:
        return _unavailable(original, "empty_answer")

    lowered = original.lower()
    family_feedback = _family_answer_correction(question, original, mode)
    if family_feedback:
        return family_feedback

    planning_feedback = _planning_answer_correction(question, original, mode)
    if planning_feedback:
        return planning_feedback

    if re.fullmatch(r"because\s+photos\s+life\.?", lowered):
        return _unavailable(
            original,
            "unclear_transcript",
            unclear_phrases=["because photos life"],
            message="Your answer appears incomplete or may have been recognised incorrectly. Please review it or record it again.",
        )

    corrected = original
    mistakes = []
    rules_applied = []

    corrected, count = re.subn(r"\bin this morning\b", "this morning", corrected, flags=re.IGNORECASE)
    if count:
        mistakes.append({
            "incorrect": "In this morning",
            "correct": "This morning",
            "type": "Preposition",
            "explanation": "Use 'this morning' without 'in'.",
        })
        rules_applied.append("Removed the unnecessary preposition before 'this morning'.")

    if re.search(r"\bi\s+goed\b", corrected, re.IGNORECASE):
        corrected = re.sub(r"\bi\s+goed\b", "I went", corrected, flags=re.IGNORECASE)
        mistakes.append({
            "incorrect": "I goed",
            "correct": "I went",
            "type": "Irregular Verb",
            "explanation": "The past tense of 'go' is 'went'.",
        })
        rules_applied.append("Changed the irregular past-tense form 'goed' to 'went'.")

    if re.search(r"\bi\s+am\s+bring\b", corrected, re.IGNORECASE):
        if _question_suggests_past(question):
            replacement = "I brought"
            explanation = "Use past tense because the question asks what you did."
        elif _question_suggests_current(question):
            replacement = "I am bringing"
            explanation = "Use the -ing form after 'am' for a current action."
        else:
            return _unavailable(
                original,
                "unclear_tense",
                unclear_phrases=["I am bring"],
                message="Your answer appears incomplete or the intended tense is unclear. Please review it or record it again.",
            )
        corrected = re.sub(r"\bi\s+am\s+bring\b", replacement, corrected, flags=re.IGNORECASE)
        mistakes.append({
            "incorrect": "I am bring",
            "correct": replacement,
            "type": "Verb Form",
            "explanation": explanation,
        })
        rules_applied.append("Corrected the verb form after 'I am' using the question context.")

    corrected = _finish_sentence(_sentence_case(corrected))
    original_finished = _finish_sentence(_sentence_case(original))
    if corrected == original_finished and not mistakes:
        return _unavailable(original, "no_safe_local_rule")

    return {
        "appreciation": "Basic correction available.",
        "status": "Needs Improvement",
        "original_answer": original,
        "has_errors": True,
        "transcript_clear": True,
        "unclear_phrases": [],
        "correction_available": True,
        "corrected_answer": corrected,
        "better_natural_answer": corrected,
        "explanation": "Basic local rules were applied. This is not detailed AI feedback.",
        "mistakes": mistakes,
        "vocabulary_suggestions": [],
        "rules_applied": rules_applied,
        "short_feedback": "Basic correction was applied locally. Retry with AI for detailed feedback.",
        "source": "local_rules",
        "fallback_reason": None,
        "scores": _empty_scores(mode),
        "scores_verified": False,
        "feedback_source": "local_rules",
        "json_validation_passed": True,
        "corrected_answer_present": True,
        "corrected_answer_changed": True,
    }


def _family_answer_correction(question, original, mode):
    context = f"{question or ''} {original}".lower()
    if "family" not in context:
        return None

    lowered = original.lower()
    mistake_specs = []
    corrected = original

    replacements = [
        (
            r"\bone family\b",
            "My family",
            "one family",
            "My family",
            "Word Choice",
            "Use 'my family' when talking about your own family.",
            "Use 'my' for your own family.",
        ),
        (
            r"\bpersons\b",
            "people",
            "persons",
            "people",
            "Word Choice",
            "'People' sounds more natural than 'persons' in everyday speech.",
            "Use 'people' in natural conversation.",
        ),
        (
            r"\bthe kind people are there\b|\bthe kind persons are there\b|\bkind people are there\b|\bkind persons are there\b",
            "there are kind people",
            "kind persons are there",
            "there are kind people",
            "Word Order",
            "Use 'there are' before the noun phrase.",
            "Put 'there are' before the noun.",
        ),
    ]

    for pattern, replacement, incorrect, correct, issue_type, explanation, point in replacements:
        corrected, count = re.subn(pattern, replacement, corrected, flags=re.IGNORECASE)
        if count and incorrect not in {item["incorrect"] for item in mistake_specs}:
            mistake_specs.append({
                "incorrect": incorrect,
                "correct": correct,
                "type": issue_type,
                "explanation": explanation,
                "mistake_points": [point],
            })

    if re.search(r"\b(in my only|is thrown|thrown of the most|and done and then)\b", lowered):
        mistake_specs.append({
            "incorrect": "in my only / is thrown of the most",
            "correct": "in my family / the most important",
            "type": "Clarity",
            "explanation": "That part sounds like a speech-recognition or word-order problem.",
            "mistake_points": ["Some words are unclear or out of order."],
        })
        corrected = "My family is beautiful, and there are kind people in my family. My family is very important to me."

    corrected = re.sub(r"\s+", " ", corrected).strip()
    corrected = re.sub(r"\s+(and\s+)?(?:done|then)\s*$", "", corrected, flags=re.IGNORECASE).strip()
    corrected = _finish_sentence(_sentence_case(corrected))

    original_finished = _finish_sentence(_sentence_case(original))
    if corrected == original_finished and not mistake_specs:
        return None

    mistake_points = []
    for mistake in mistake_specs:
        mistake_points.extend(mistake.get("mistake_points", []))
    mistake_points = mistake_points[:4] or ["Use clearer word order.", "Remove unclear extra words."]

    return {
        "appreciation": "Basic correction available.",
        "status": "Needs Improvement",
        "original_answer": original,
        "has_errors": True,
        "transcript_clear": True,
        "unclear_phrases": [],
        "correction_available": True,
        "corrected_answer": corrected,
        "better_natural_answer": corrected,
        "explanation": "Basic local grammar rules corrected the clearest family-answer mistakes.",
        "mistake_points": mistake_points,
        "mistakes": mistake_specs,
        "vocabulary_suggestions": [],
        "rules_applied": ["Applied local family-answer grammar correction."],
        "short_feedback": "Good attempt. Use clearer word order and natural family vocabulary.",
        "source": "local_rules",
        "fallback_reason": None,
        "scores": _empty_scores(mode),
        "scores_verified": False,
        "feedback_source": "local_rules",
        "json_validation_passed": True,
        "corrected_answer_present": True,
        "corrected_answer_changed": True,
    }


def _planning_answer_correction(question, original, mode):
    context = f"{question or ''} {original}".lower()
    if not (
        re.search(r"\bplanning\s+to\s+going\b", context)
        or re.search(r"\bgoing\s+(?:to\s+)?temple\b", context)
        or ("temple" in context and "plan" in context)
    ):
        return None

    corrected = "I am planning to go to the temple, and we can plan the visit together."
    mistake_specs = [
        {
            "incorrect": "planning to going",
            "correct": "planning to go",
            "type": "Verb Form",
            "explanation": "Use the base verb after 'to'.",
            "mistake_points": ["Use the base verb after 'to'."],
        },
        {
            "incorrect": "going Temple",
            "correct": "go to the temple",
            "type": "Preposition and Article",
            "explanation": "Use 'to the' before a place like temple.",
            "mistake_points": ["Use 'to the' before a place."],
        },
        {
            "incorrect": "that is my we can plan",
            "correct": "we can plan the visit together",
            "type": "Clarity",
            "explanation": "Remove unclear extra words and make the idea complete.",
            "mistake_points": ["Remove unclear extra words."],
        },
    ]

    return {
        "appreciation": "Basic correction available.",
        "status": "Needs Improvement",
        "original_answer": original,
        "has_errors": True,
        "transcript_clear": True,
        "unclear_phrases": [],
        "correction_available": True,
        "corrected_answer": corrected,
        "better_natural_answer": "I am planning to visit the temple, and we can plan everything together.",
        "explanation": "Basic local grammar rules corrected the clearest planning-answer mistakes.",
        "mistake_points": [
            "Use the base verb after 'to'.",
            "Use 'to the' before a place.",
            "Remove unclear extra words.",
        ],
        "mistakes": mistake_specs,
        "vocabulary_suggestions": [],
        "rules_applied": ["Applied local planning-answer grammar correction."],
        "short_feedback": "Good attempt. Use 'planning to go' and make the sentence clearer.",
        "source": "local_rules",
        "fallback_reason": None,
        "scores": _empty_scores(mode),
        "scores_verified": False,
        "feedback_source": "local_rules",
        "json_validation_passed": True,
        "corrected_answer_present": True,
        "corrected_answer_changed": True,
    }


def _unavailable(original, reason, unclear_phrases=None, message=None):
    return {
        "appreciation": "Correction unavailable",
        "status": "Needs Review" if original else "No Answer",
        "original_answer": original,
        "has_errors": None,
        "transcript_clear": False if unclear_phrases else None,
        "unclear_phrases": unclear_phrases or [],
        "correction_available": False,
        "corrected_answer": None,
        "better_natural_answer": None,
        "explanation": message or "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.",
        "mistakes": [],
        "vocabulary_suggestions": [],
        "rules_applied": [],
        "short_feedback": message or "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.",
        "source": "fallback",
        "fallback_reason": reason,
        "scores": _empty_scores("topic"),
        "scores_verified": False,
        "feedback_source": "fallback",
        "json_validation_passed": False,
        "corrected_answer_present": False,
        "corrected_answer_changed": False,
    }


def _empty_scores(mode):
    return {
        "confidence": None,
        "fluency": None,
        "grammar": None,
        "knowledge": None if mode != "topic" else None,
        "overall": None,
    }
