import re
from difflib import SequenceMatcher


ASSESSMENT_TYPE = "speech_recognition_match"

# Priority 2: Simple rule-based mapping for ESL problem sounds
def extract_sound_issues(words):
    issues = set()
    for w in words:
        w_lower = w.lower()
        if "th" in w_lower:
            issues.add("th sound")
        if "v" in w_lower or "w" in w_lower:
            issues.add("v/w confusion")
        if w_lower.startswith("r") or ("r" in w_lower and w_lower[w_lower.find("r")-1] not in "aeiou"):
            issues.add("r sound")
        if "sh" in w_lower or "ch" in w_lower:
            issues.add("sh/ch sounds")
        if w_lower.endswith("ed"):
            issues.add("final -ed ending")
        if w_lower.endswith("s"):
            issues.add("final -s ending")
        if "l" in w_lower and "r" in w_lower:
            issues.add("l/r confusion")
    return list(issues)


def _clamp10(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return round(max(0.0, min(number, 10.0)), 1)


def normalize_text(text):
    value = (text or "").lower().strip()
    value = re.sub(r"[^\w\s']", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _tokenize(text):
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def _duration_score(expected_words, duration_seconds):
    if not duration_seconds:
        return 7.0
    expected = max(1.5, expected_words * 0.55)
    ratio = duration_seconds / expected
    if 0.65 <= ratio <= 1.8:
        return 9.0
    if 0.45 <= ratio <= 2.4:
        return 7.0
    return 5.0


def assess_pronunciation(expected_text, recognised_text, recognition_confidence=None, duration_seconds=None, mode=None, minimal_pairs_target=None):
    expected = _tokenize(expected_text)
    recognised = _tokenize(recognised_text)
    matcher = SequenceMatcher(a=expected, b=recognised, autojunk=False)

    correct_words = []
    missing_words = []
    different_words = []
    extra_words = []
    word_results = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        expected_slice = expected[i1:i2]
        recognised_slice = recognised[j1:j2]
        if tag == "equal":
            for word in expected_slice:
                correct_words.append(word)
                word_results.append({"word": word, "recognised": word, "status": "Correct"})
        elif tag == "delete":
            for word in expected_slice:
                missing_words.append(word)
                word_results.append({"word": word, "recognised": "", "status": "Missing"})
        elif tag == "insert":
            for word in recognised_slice:
                extra_words.append(word)
                word_results.append({"word": word, "recognised": word, "status": "Extra"})
        else:
            max_len = max(len(expected_slice), len(recognised_slice))
            for index in range(max_len):
                exp_word = expected_slice[index] if index < len(expected_slice) else ""
                rec_word = recognised_slice[index] if index < len(recognised_slice) else ""
                if exp_word and rec_word:
                    different_words.append({"expected": exp_word, "recognised": rec_word})
                    word_results.append({"word": exp_word, "recognised": rec_word, "status": "Different"})
                elif exp_word:
                    missing_words.append(exp_word)
                    word_results.append({"word": exp_word, "recognised": "", "status": "Missing"})
                elif rec_word:
                    extra_words.append(rec_word)
                    word_results.append({"word": rec_word, "recognised": rec_word, "status": "Extra"})

    expected_count = len(expected)
    recognised_expected_matches = len(correct_words)
    attempted_expected_words = recognised_expected_matches
    word_accuracy = _clamp10((recognised_expected_matches / expected_count) * 10 if expected_count else 0)

    # Completeness must mean "how much of the reference was correctly recognised".
    # A replacement like "conversation" -> "communication" is an attempted word, but
    # it is not a completed reference word. The old formula treated replacements as
    # complete because they were not missing, which inflated clearly wrong attempts.
    completeness = _clamp10((attempted_expected_words / expected_count) * 10 if expected_count else 0)

    confidence_score = None
    if recognition_confidence is not None:
        try:
            confidence_score = float(recognition_confidence) * 10
        except (TypeError, ValueError):
            confidence_score = None
    clarity_base = word_accuracy if confidence_score is None else (word_accuracy * 0.65 + confidence_score * 0.35)
    clarity = _clamp10(clarity_base)
    fluency = _clamp10((_duration_score(expected_count, duration_seconds) * 0.55) + (completeness * 0.45))
    overall = _clamp10((word_accuracy * 0.4) + (completeness * 0.25) + (clarity * 0.2) + (fluency * 0.15))

    if expected_count and recognised and recognised_expected_matches == 0:
        # If none of the target words were recognised, keep rhythm/confidence from
        # making the result look like a pass. This is especially important in word
        # practice where a different word can still be spoken fluently.
        overall = min(overall, 1.5 if expected_count == 1 else 2.0)
        fluency = min(fluency, 4.0)

    match_percentage = int(round(overall * 10))

    needs_practice = [item["word"] for item in word_results if item["status"] in {"Missing", "Different"}]
    exact_match = expected == recognised and bool(expected)
    validation_message = (
        "The recognised speech does not match the reference word."
        if expected_count == 1 and recognised and not exact_match
        else "The recognised speech was compared with the reference text."
    )

    if mode == "minimal_pairs" and minimal_pairs_target:
        # Priority 7: Explicitly flag if they said the other word in the pair
        # minimal_pairs_target is a tuple or list: (target_word, wrong_word)
        target_w, wrong_w = minimal_pairs_target
        if wrong_w in recognised:
            validation_message = f"You said '{wrong_w}' instead of '{target_w}'."
            # Penalize
            overall = min(overall, 3.0)
            word_accuracy = 0.0
            match_percentage = int(round(overall * 10))

    return {
        "assessment_type": ASSESSMENT_TYPE,
        "exact_match": exact_match,
        "validation_message": validation_message,
        "match_percentage": match_percentage,
        "scores": {
            "word_accuracy": word_accuracy,
            "completeness": completeness,
            "clarity": clarity,
            "fluency": fluency,
            "overall": overall,
        },
        "expected_text": expected_text,
        "recognised_text": recognised_text,
        "correct_words": correct_words,
        "missing_words": missing_words,
        "different_words": different_words,
        "extra_words": extra_words,
        "words_needing_practice": needs_practice,
        "word_results": word_results,
        "sound_tags": extract_sound_issues(needs_practice),
    }
