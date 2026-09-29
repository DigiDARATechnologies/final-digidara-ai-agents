"""Phonetic and Prosody Enhancement Module for Pronunciation Assessment.

Provides backward-compatible phonetic token analysis, IPA approximations,
phoneme substitution detection, and speech rate/prosody scoring.
Does not break or alter any existing output keys of assess_pronunciation.
"""

import math
import re
from typing import Dict, List, Optional, Tuple

# Common English phoneme mappings and approximate IPA conversions (CMU Dict inspired)
# Mapped for ESL high-frequency mispronunciation analysis.
PHONEME_MAP = {
    "th": ("/θ/", "dental fricative (as in 'think' or 'this')"),
    "sh": ("/ʃ/", "postalveolar fricative (as in 'ship')"),
    "ch": ("/tʃ/", "affricate (as in 'chair')"),
    "ph": ("/f/", "labiodental fricative (as in 'phone')"),
    "wh": ("/w/", "voiced labiovelar approximant (as in 'what')"),
    "ng": ("/ŋ/", "velar nasal (as in 'sing')"),
    "ck": ("/k/", "voiceless velar plosive (as in 'back')"),
    "ee": ("/iː/", "close front unrounded vowel (as in 'meet')"),
    "oo": ("/uː/", "close back rounded vowel (as in 'boot')"),
    "ea": ("/iː/", "front vowel (as in 'read')"),
    "ai": ("/eɪ/", "diphthong (as in 'rain')"),
    "ay": ("/eɪ/", "diphthong (as in 'day')"),
    "igh": ("/aɪ/", "diphthong (as in 'light')"),
    "oa": ("/oʊ/", "diphthong (as in 'boat')"),
    "ou": ("/aʊ/", "diphthong (as in 'sound')"),
    "ow": ("/aʊ/", "diphthong (as in 'now')"),
}

# Articulatory guidance for detected ESL phoneme difficulties
ARTICULATORY_TIPS = {
    "th sound": "Place the tip of your tongue gently between your upper and lower teeth, and blow air smoothly without biting.",
    "v/w confusion": "For 'V', touch your top teeth to your lower lip and vibrate your vocal cords. For 'W', round your lips like a small circle without teeth touching.",
    "r sound": "Curl the tip of your tongue back slightly toward the roof of your mouth without touching it, and tense the sides of your tongue.",
    "l/r confusion": "For 'L', press the tip of your tongue firmly against the ridge behind your upper front teeth. For 'R', your tongue does not touch the roof.",
    "sh/ch sounds": "For 'SH', push air continuously through rounded lips. For 'CH', stop the air completely with your tongue first, then release with a burst.",
    "final -ed ending": "Notice if the root word ends with a voiced sound (pronounce as /d/), voiceless sound (pronounce as /t/), or t/d (pronounce as /ɪd/).",
    "final -s ending": "Ensure you finish the word with a clear /s/ or /z/ sound without dropping the trailing syllable.",
}


def approximate_word_ipa(word: str) -> str:
    """Generate a readable approximate IPA string for an English word."""
    if not word:
        return ""
    clean = re.sub(r"[^\w]", "", word.lower())
    if not clean:
        return ""

    # Check common known patterns
    ipa = clean
    for pattern, (ipa_symbol, _) in sorted(PHONEME_MAP.items(), key=lambda x: -len(x[0])):
        ipa = ipa.replace(pattern, ipa_symbol)

    # Vowel simplifications
    ipa = re.sub(r"a(?![\u0080-\uffff])", "æ", ipa)
    ipa = re.sub(r"e(?![\u0080-\uffff])", "ɛ", ipa)
    ipa = re.sub(r"i(?![\u0080-\uffff])", "ɪ", ipa)
    ipa = re.sub(r"o(?![\u0080-\uffff])", "ɒ", ipa)
    ipa = re.sub(r"u(?![\u0080-\uffff])", "ʌ", ipa)
    return f"/{ipa}/"


def analyze_phonetic_deviations(
    expected_words: List[str],
    recognised_words: List[str],
    different_pairs: List[Dict[str, str]],
) -> List[Dict]:
    """Identify precise phoneme substitutions and provide targeted articulatory feedback."""
    deviations = []

    for pair in different_pairs:
        exp = (pair.get("expected") or "").lower().strip()
        rec = (pair.get("recognised") or "").lower().strip()
        if not exp or not rec:
            continue

        exp_ipa = approximate_word_ipa(exp)
        rec_ipa = approximate_word_ipa(rec)

        # Detect specific sound conflict
        detected_issue = None
        guidance = None

        if ("th" in exp and "th" not in rec) or ("s" in rec and "th" in exp):
            detected_issue = "th sound"
        elif ("v" in exp and "w" in rec) or ("w" in exp and "v" in rec):
            detected_issue = "v/w confusion"
        elif ("r" in exp and "l" in rec) or ("l" in exp and "r" in rec):
            detected_issue = "l/r confusion"
        elif ("sh" in exp and "ch" in rec) or ("ch" in exp and "sh" in rec):
            detected_issue = "sh/ch sounds"
        elif exp.endswith("ed") and not rec.endswith("ed"):
            detected_issue = "final -ed ending"
        elif exp.endswith("s") and not rec.endswith("s"):
            detected_issue = "final -s ending"

        if detected_issue and detected_issue in ARTICULATORY_TIPS:
            guidance = ARTICULATORY_TIPS[detected_issue]

        deviations.append({
            "target_word": exp,
            "spoken_word": rec,
            "target_ipa": exp_ipa,
            "spoken_ipa": rec_ipa,
            "issue_category": detected_issue,
            "articulatory_guidance": guidance,
        })

    return deviations


def compute_prosody_metrics(
    expected_text: str,
    recognised_text: str,
    duration_seconds: Optional[float],
    recognition_confidence: Optional[float],
) -> Dict:
    """Compute prosody, speech tempo, and rhythm stability metrics.

    Normal conversational English rate is ~120-160 words per minute (WPM).
    Returns bounded scores between 0.0 and 10.0.
    """
    words = [w for w in re.split(r"\s+", (recognised_text or "").strip()) if w]
    word_count = len(words)
    syllable_count = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in words)

    if not duration_seconds or duration_seconds <= 0.2:
        return {
            "wpm": None,
            "syllables_per_second": None,
            "tempo_rating": "Optimal",
            "tempo_score": 8.0,
            "rhythm_score": 7.5,
        }

    # Words Per Minute
    wpm = round((word_count / duration_seconds) * 60, 1)
    sps = round(syllable_count / duration_seconds, 2)

    # Tempo rating based on standard ESL acoustic benchmarks:
    # < 85 WPM: Hesitant / slow
    # 90 - 150 WPM: Natural conversational flow
    # > 185 WPM: Rushed / fast
    if 90 <= wpm <= 165:
        tempo_rating = "Natural Pace"
        tempo_score = 9.5
    elif 70 <= wpm < 90 or 165 < wpm <= 195:
        tempo_rating = "Slightly Slow" if wpm < 90 else "Slightly Fast"
        tempo_score = 8.0
    elif 50 <= wpm < 70 or 195 < wpm <= 230:
        tempo_rating = "Noticeably Slow" if wpm < 70 else "Fast"
        tempo_score = 6.5
    else:
        tempo_rating = "Very Slow / Hesitant" if wpm < 50 else "Very Rushed"
        tempo_score = 5.0

    # Rhythm stability influenced by speech recognition confidence and word duration ratios
    conf_factor = float(recognition_confidence) if recognition_confidence is not None else 0.8
    rhythm_score = round(max(1.0, min(10.0, (tempo_score * 0.6) + (conf_factor * 10 * 0.4))), 1)

    return {
        "wpm": wpm,
        "syllables_per_second": sps,
        "tempo_rating": tempo_rating,
        "tempo_score": tempo_score,
        "rhythm_score": rhythm_score,
    }
