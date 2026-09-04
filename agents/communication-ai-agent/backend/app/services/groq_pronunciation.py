import json
from datetime import date

from flask import current_app

from .groq_common import FALLBACK_PRONUNCIATION_ITEMS, _chat, _extract_json

DAILY_CHALLENGE_SCHEMA_VERSION = "daily_challenge_v2"

# Priority 7: Minimal Pairs Seed Data
MINIMAL_PAIRS_DATA = {
    "easy": [
        {"pair": ["pen", "pan"], "meaning": "Writing tool vs Cooking tool"},
        {"pair": ["ship", "sheep"], "meaning": "Boat vs Animal"},
        {"pair": ["bit", "beat"], "meaning": "Small piece vs To strike or win"},
        {"pair": ["live", "leave"], "meaning": "To be alive vs To go away"},
        {"pair": ["bad", "bed"], "meaning": "Not good vs Furniture for sleeping"}
    ],
    "medium": [
        {"pair": ["thin", "tin"], "meaning": "Not thick vs Metal container"},
        {"pair": ["wine", "vine"], "meaning": "Drink vs Climbing plant"},
        {"pair": ["berry", "very"], "meaning": "Small fruit vs Much"},
        {"pair": ["pool", "pull"], "meaning": "Water for swimming vs To draw towards"},
        {"pair": ["coat", "caught"], "meaning": "Clothing vs Past tense of catch"}
    ],
    "hard": [
        {"pair": ["weather", "whether"], "meaning": "Climate vs If"},
        {"pair": ["affect", "effect"], "meaning": "To influence vs Result"},
        {"pair": ["desert", "dessert"], "meaning": "Dry land vs Sweet food"},
        {"pair": ["bought", "boat"], "meaning": "Past tense of buy vs Watercraft"},
        {"pair": ["choose", "shoes"], "meaning": "To pick vs Footwear"}
    ]
}

FALLBACK_DAILY_CHALLENGES = {
    "easy": [
        {
            "title": "Morning Routine",
            "description": "Practise three simple sentences about your morning.",
            "practice_lines": ["I wake up at seven.", "I drink a glass of water.", "I get ready for work."],
            "instructions": ["Listen to all three lines.", "Repeat each line clearly.", "Speak slowly."],
            "goal": "Repeat all three sentences clearly.",
            "expected_duration_seconds": 20,
        },
        {
            "title": "Greeting a Friend",
            "description": "Practise a short friendly greeting.",
            "practice_lines": ["Hi, how are you?", "It is nice to see you.", "Have a good day."],
            "instructions": ["Listen once.", "Repeat with a friendly tone.", "Keep final sounds clear."],
            "goal": "Greet a friend clearly and confidently.",
            "expected_duration_seconds": 18,
        },
    ],
    "medium": [
        {
            "title": "Professional Self-Introduction",
            "description": "Practise introducing yourself in a workplace setting.",
            "practice_lines": [
                "Hello, my name is Harini.",
                "I am learning Python full-stack development.",
                "I enjoy building practical software applications.",
                "My goal is to grow as a software developer.",
            ],
            "instructions": ["Listen once.", "Repeat all lines clearly.", "Focus on natural pauses.", "Maintain a confident pace."],
            "goal": "Deliver a clear professional introduction.",
            "expected_duration_seconds": 35,
        },
        {
            "title": "Giving a Work Update",
            "description": "Practise sharing a short workplace progress update.",
            "practice_lines": [
                "I completed the first part of the task.",
                "I am reviewing the remaining details today.",
                "I will share the final update before the meeting.",
            ],
            "instructions": ["Pause after each sentence.", "Stress action words.", "Keep your pace steady."],
            "goal": "Give a clear and natural work update.",
            "expected_duration_seconds": 30,
        },
    ],
    "hard": [
        {
            "title": "Project Presentation Opening",
            "description": "Practise introducing a software project professionally.",
            "practice_lines": [
                "Today, I would like to present our communication development module.",
                "The system helps learners improve speaking, writing and pronunciation.",
                "It provides personalised feedback and tracks learning progress.",
                "Our goal is to create a practical and accessible learning experience.",
            ],
            "instructions": ["Use clear pauses.", "Emphasise important words.", "Maintain a professional tone.", "Avoid speaking too quickly."],
            "goal": "Present all lines with clarity and confidence.",
            "expected_duration_seconds": 50,
        },
        {
            "title": "Handling a Workplace Conflict",
            "description": "Practise a calm and professional response to disagreement.",
            "practice_lines": [
                "I understand that we have different opinions about the project timeline.",
                "Let us review the main concerns and agree on practical next steps.",
                "Clear communication will help us resolve the issue professionally.",
            ],
            "instructions": ["Use a calm tone.", "Pause before key points.", "Emphasise professional language."],
            "goal": "Respond to conflict with clarity and control.",
            "expected_duration_seconds": 45,
        },
    ],
}


def _fallback_daily_challenge(difficulty, recent_items=None):
    recent = {str(item).strip().lower() for item in (recent_items or [])}
    selected = next(
        (item for item in FALLBACK_DAILY_CHALLENGES[difficulty] if item["title"].strip().lower() not in recent),
        FALLBACK_DAILY_CHALLENGES[difficulty][0],
    )
    metadata = {**selected, "schema_version": DAILY_CHALLENGE_SCHEMA_VERSION}
    text = "\n".join(selected["practice_lines"])
    return {
        "text": text,
        "item_type": "sentence",
        "meaning": selected["title"],
        "example_sentence": selected["practice_lines"][0],
        "difficulty": difficulty,
        "expected_duration_seconds": selected["expected_duration_seconds"],
        "syllables": None,
        "source": "fallback",
        "metadata": metadata,
    }


def _fallback_pronunciation_item(mode, difficulty, recent_items=None):
    if mode == "daily":
        daily = _fallback_daily_challenge(difficulty, recent_items)
        return {
            **daily,
        }

    item_mode = "sentence" if mode == "sentence" else "word"
    candidates = FALLBACK_PRONUNCIATION_ITEMS[(item_mode, difficulty)]
    recent = {str(item).strip().lower() for item in (recent_items or [])}
    selected = next((item for item in candidates if item[0].lower() not in recent), candidates[0])
    text, meaning, example, item_type, duration, syllables = selected
    return {
        "text": text,
        "item_type": item_type,
        "meaning": meaning,
        "example_sentence": example,
        "difficulty": difficulty,
        "expected_duration_seconds": duration,
        "syllables": syllables,
        "source": "fallback",
        "metadata": {
            "focus_tip": "Listen once, practise slowly, then repeat at a natural speed.",
            "difficult_words": [text] if item_type == "word" else [],
        },
    }


def generate_pronunciation_item(practice_mode, difficulty, recent_items=None):
    if practice_mode == "minimal_pairs":
        import random
        # Priority 7: Generate minimal pairs
        pool = MINIMAL_PAIRS_DATA.get(difficulty, MINIMAL_PAIRS_DATA["medium"])
        # To avoid repeats, filter pool
        recent = {str(item).strip().lower() for item in (recent_items or [])}
        available = [p for p in pool if p["pair"][0] not in recent and p["pair"][1] not in recent]
        if not available:
            available = pool
        selected = random.choice(available)
        word_a, word_b = selected["pair"]
        contrast = _minimal_pair_contrast(word_a, word_b)
        return {
            "text": f"{word_a} / {word_b}",
            "item_type": "word",
            "meaning": selected["meaning"],
            "example_sentence": None,
            "difficulty": difficulty,
            "expected_duration_seconds": 8,
            "syllables": None,
            "metadata": {
                "pair": selected["pair"],
                "word_a": word_a,
                "word_b": word_b,
                "sound_contrast": contrast,
                "practice_sequence": selected["pair"],
                "interaction": "sequential_production",
                "title": f"Minimal Pair: {selected['pair'][0]} / {selected['pair'][1]}"
            },
            "source": "static"
        }

    if practice_mode == "daily":
        return generate_daily_pronunciation_challenge(difficulty, date.today(), recent_items)

    item_type = "word" if practice_mode == "word" else "sentence"
    prompt_mode = "daily_challenge" if practice_mode == "daily" else practice_mode
    system_prompt = (
        "You are an English pronunciation practice teacher.\n\n"
        "Generate exactly one pronunciation practice item.\n\n"
        "Practice mode:\n"
        f"{prompt_mode}\n\n"
        "Difficulty:\n"
        f"{difficulty}\n\n"
        "Recent items that must not be repeated:\n"
        f"{recent_items or []}\n\n"
        "Rules for Word Practice:\n\n"
        "Easy:\n"
        "- Use common everyday English words.\n"
        "- Use short or simple words.\n"
        "- Avoid complex syllable combinations.\n\n"
        "Medium:\n"
        "- Use communication, education, workplace or career vocabulary.\n"
        "- Use moderately challenging multisyllable words.\n\n"
        "Hard:\n"
        "- Use professional and advanced vocabulary.\n"
        "- Include complex but useful pronunciation patterns.\n"
        "- Avoid rare or obscure words.\n\n"
        "Rules for Sentence Practice:\n\n"
        "Easy:\n"
        "- Use one short everyday sentence.\n"
        "- Use simple vocabulary.\n"
        "- Maximum 8 words.\n\n"
        "Medium:\n"
        "- Use one natural sentence about education, work or communication.\n"
        "- Use moderate vocabulary.\n"
        "- Between 8 and 15 words.\n\n"
        "Hard:\n"
        "- Use one professional or analytical sentence.\n"
        "- Use complex but natural English.\n"
        "- Between 12 and 22 words.\n\n"
        "Rules for Daily Challenge:\n\n"
        "Easy:\n"
        "- Create a simple daily-life pronunciation task.\n"
        "- Include 2 or 3 short sentences.\n\n"
        "Medium:\n"
        "- Create a workplace, college or career-based mini challenge.\n"
        "- Include a short speaking goal.\n\n"
        "Hard:\n"
        "- Create a professional presentation, interview or workplace challenge.\n"
        "- Include structured pronunciation practice.\n\n"
        "Return valid JSON only.\n\n"
        "For Word Practice:\n\n"
        "{\n"
        '  "mode": "word",\n'
        '  "title": "Communication",\n'
        '  "text": "Communication",\n'
        '  "meaning": "The sharing of information or ideas.",\n'
        '  "example_sentence": "Good communication helps teams work well.",\n'
        '  "difficulty": "medium"\n'
        "}\n\n"
        "For Sentence Practice:\n\n"
        "{\n"
        '  "mode": "sentence",\n'
        '  "title": "Sentence Practice",\n'
        '  "text": "Effective communication helps teams work successfully.",\n'
        '  "meaning": null,\n'
        '  "example_sentence": null,\n'
        '  "difficulty": "medium"\n'
        "}\n\n"
        "For Daily Challenge:\n\n"
        "{\n"
        '  "mode": "daily_challenge",\n'
        '  "title": "Professional Introduction",\n'
        '  "text": "Hello, my name is Harini. I am a Python full-stack developer.",\n'
        '  "instructions": [\n'
        '    "Listen once",\n'
        '    "Repeat both sentences",\n'
        '    "Focus on clear word endings"\n'
        "  ],\n"
        '  "difficulty": "medium"\n'
        "}\n\n"
        "Do not return markdown.\n"
        "Do not use code fences.\n"
        "Do not repeat recent items."
    )
    try:
        data = _extract_json(_chat(system_prompt, "Generate the item now.", temperature=0.6, operation="pronunciation.daily_challenge_generation" if practice_mode == "daily" else "pronunciation.content_generation", module="pronunciation", service="groq_pronunciation.generate_pronunciation_item"))
        practice_lines = data.get("practice_lines") if isinstance(data.get("practice_lines"), list) else []
        text = str(data.get("practice_text") or data.get("text") or "").strip()
        if practice_mode == "daily" and practice_lines:
            text = "\n".join(str(line).strip() for line in practice_lines if str(line).strip())
        if not text:
            raise ValueError("Missing pronunciation text")
        if practice_mode == "word" and len(text.split()) != 1:
            raise ValueError("Word practice returned multiple words")
        if practice_mode in {"sentence", "daily"} and len(text.split()) < 3:
            raise ValueError("Sentence practice returned too little text")
        instructions = data.get("instructions") if isinstance(data.get("instructions"), list) else []
        title = str(data.get("title") or ("Daily Challenge" if practice_mode == "daily" else "Sentence Practice")).strip()
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        if practice_mode == "daily":
            lines = practice_lines or [line.strip() for line in text.splitlines() if line.strip()] or [text]
            metadata = {
                **metadata,
                "title": title,
                "description": str(data.get("description") or "").strip()[:500],
                "practice_lines": lines,
                "main_sentence": text,
                "challenge_phrase": " ".join(text.split()[-4:]).strip(" .,!?") or text,
                "focus_tip": instructions[-1] if instructions else "Repeat the sentences clearly and focus on word endings.",
                "instructions": instructions,
                "goal": str(data.get("goal") or "").strip()[:240],
                "speaking_goal": instructions[1] if len(instructions) > 1 else "Repeat the full challenge clearly.",
                "why_today": title,
            }
        elif practice_mode == "sentence":
            metadata = {
                **metadata,
                "title": title,
                "speaking_goal": "Say the full sentence clearly and naturally.",
                "focus_tip": "Keep every important word clear.",
                "difficult_words": [word.strip(".,!?") for word in text.split() if len(word.strip(".,!?")) >= 7][:4],
            }
        else:
            metadata = {
                **metadata,
                "title": title,
                "syllables": data.get("syllables") if isinstance(data.get("syllables"), list) else None,
                "focus_tip": "Listen once, practise slowly, then repeat at a natural speed.",
                "sound_focus": "Clear word stress and ending sounds.",
            }
        return {
            "text": text[:500],
            "item_type": item_type,
            "meaning": str(data.get("meaning") or (title if practice_mode == "daily" else "")).strip()[:500],
            "example_sentence": str(data.get("example_sentence") or metadata.get("challenge_phrase") or "").strip()[:500],
            "difficulty": difficulty,
            "expected_duration_seconds": int(data.get("expected_duration_seconds") or (4 if item_type == "word" else 7)),
            "syllables": "-".join(data.get("syllables")) if isinstance(data.get("syllables"), list) else data.get("syllables") if isinstance(data.get("syllables"), str) else None,
            "metadata": metadata,
            "source": "groq",
        }
    except Exception:
        return _fallback_pronunciation_item(practice_mode, difficulty, recent_items)


def _minimal_pair_contrast(word_a, word_b):
    for index, (left, right) in enumerate(zip(word_a, word_b)):
        if left != right:
            return f"{left} vs {right}"
    if len(word_a) != len(word_b):
        return "word length contrast"
    return "single sound contrast"


def generate_daily_pronunciation_challenge(difficulty, challenge_date, recent_challenges=None):
    system_prompt = (
        "You are an English pronunciation teacher creating one daily pronunciation challenge.\n\n"
        "Practice mode:\n\n"
        "Daily Challenge\n\n"
        "Selected difficulty:\n\n"
        f"{difficulty}\n\n"
        "Challenge date:\n\n"
        f"{challenge_date}\n\n"
        "Recent challenges that must not be repeated:\n\n"
        f"{recent_challenges or []}\n\n"
        "Generate exactly one challenge for the selected difficulty.\n\n"
        "Easy rules:\n\n"
        "- Use a familiar daily-life situation.\n"
        "- Include two or three short sentences.\n"
        "- Use simple vocabulary.\n"
        "- Focus on clear speech and confidence.\n"
        "- Expected duration: 15 to 25 seconds.\n\n"
        "Medium rules:\n\n"
        "- Use a college, career or workplace situation.\n"
        "- Include three or four connected sentences.\n"
        "- Use moderately challenging vocabulary.\n"
        "- Focus on natural pauses and complete word endings.\n"
        "- Expected duration: 25 to 40 seconds.\n\n"
        "Hard rules:\n\n"
        "- Use a professional presentation, interview, leadership or workplace situation.\n"
        "- Include three to five connected sentences.\n"
        "- Use advanced but natural vocabulary.\n"
        "- Focus on pace, emphasis and professional delivery.\n"
        "- Expected duration: 40 to 60 seconds.\n\n"
        "Return valid JSON only:\n\n"
        "{\n"
        '  "title": "Challenge title",\n'
        '  "description": "Short challenge description",\n'
        '  "practice_lines": [\n'
        '    "First practice line",\n'
        '    "Second practice line"\n'
        "  ],\n"
        '  "instructions": [\n'
        '    "First instruction",\n'
        '    "Second instruction"\n'
        "  ],\n"
        '  "goal": "Clear completion goal",\n'
        '  "expected_duration_seconds": 30\n'
        "}\n\n"
        "Rules:\n\n"
        "1. Do not return markdown.\n"
        "2. Do not use code fences.\n"
        "3. Do not repeat a recent challenge.\n"
        "4. Match the selected difficulty.\n"
        "5. Do not return only one word.\n"
        "6. Do not return an unrelated paragraph.\n"
        "7. Keep all practice lines connected to the same scenario.\n"
        "8. Make the content useful for real communication.\n"
        "9. Return English content only."
    )
    try:
        data = _extract_json(_chat(system_prompt, "Generate today's challenge now.", temperature=0.6, operation="pronunciation.daily_challenge_generation", module="pronunciation", service="groq_pronunciation.generate_daily_pronunciation_challenge"))
        title = str(data.get("title") or "").strip()
        lines = [str(line).strip() for line in data.get("practice_lines", []) if str(line).strip()] if isinstance(data.get("practice_lines"), list) else []
        instructions = [str(item).strip() for item in data.get("instructions", []) if str(item).strip()] if isinstance(data.get("instructions"), list) else []
        duration = int(data.get("expected_duration_seconds") or 0)
        minimum_lines = 2 if difficulty == "easy" else 3
        maximum_lines = 3 if difficulty == "easy" else 4 if difficulty == "medium" else 5
        if not title or len(lines) < minimum_lines or len(lines) > maximum_lines:
            raise ValueError("Daily challenge content did not match the selected difficulty.")
        if not instructions or not data.get("goal"):
            raise ValueError("Daily challenge is missing instructions or goal.")
        if difficulty == "easy" and not 15 <= duration <= 25:
            duration = 20
        elif difficulty == "medium" and not 25 <= duration <= 40:
            duration = 35
        elif difficulty == "hard" and not 40 <= duration <= 60:
            duration = 50
        metadata = {
            "schema_version": DAILY_CHALLENGE_SCHEMA_VERSION,
            "title": title,
            "description": str(data.get("description") or "").strip()[:500],
            "practice_lines": lines,
            "instructions": instructions,
            "goal": str(data.get("goal") or "").strip()[:240],
            "focus_tip": instructions[-1],
            "challenge_phrase": lines[0],
            "main_sentence": "\n".join(lines),
        }
        return {
            "text": "\n".join(lines)[:500],
            "item_type": "sentence",
            "meaning": title[:500],
            "example_sentence": lines[0][:500],
            "difficulty": difficulty,
            "expected_duration_seconds": duration,
            "syllables": None,
            "metadata": metadata,
            "source": "groq",
        }
    except Exception:
        return _fallback_daily_challenge(difficulty, recent_challenges)


def generate_pronunciation_feedback(reference_text, recognised_text, comparison_results, difficulty):
    system_prompt = (
        "You are a friendly English pronunciation practice teacher. Return valid JSON only. "
        "Do not claim certified phonetic accuracy and do not change calculated scores."
    )
    user_prompt = (
        f"Reference text: {reference_text}\n"
        f"Recognised user text: {recognised_text}\n"
        f"Deterministic comparison: {json.dumps(comparison_results)}\n"
        f"Difficulty: {difficulty}\n\n"
        "Explain important differences simply. Mention correct parts, words needing practice, one short practical tip, "
        "and one next instruction. Return JSON:\n"
        '{"appreciation":"Good attempt.","feedback":"Your sentence was mostly clear.",'
        '"words_to_practice":[{"word":"skills","reason":"The word was not clearly recognised."}],'
        '"practice_tip":"Say the final word slowly, then repeat the full sentence.",'
        '"next_instruction":"Listen once more and try again."}'
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.4, operation="pronunciation.feedback_generation", module="pronunciation", service="groq_pronunciation.generate_pronunciation_feedback"))
    except Exception:
        data = {}
    words = data.get("words_to_practice") if isinstance(data.get("words_to_practice"), list) else []
    fallback_words = [
        {"word": word, "reason": "This word was missing or recognised differently."}
        for word in comparison_results.get("words_needing_practice", [])[:3]
    ]
    return {
        "appreciation": data.get("appreciation") or "Good attempt.",
        "feedback": data.get("feedback") or "Speech Match compares the reference text with the words recognised from your speech.",
        "words_to_practice": words[:4] if words else fallback_words,
        "practice_tip": data.get("practice_tip") or "Listen once, say it slowly, then repeat at a natural speed.",
        "next_instruction": data.get("next_instruction") or "Try again and focus on the words marked Needs Practice.",
    }


def summarize_pronunciation_session(turn_results, difficulty):
    """Generate a session-level summary from per-question attempt results.

    Args:
        turn_results: list of dicts with keys: turn_number, reference_text,
                      recognised_text, overall_score, feedback (dict).
        difficulty: 'easy' | 'medium' | 'hard'

    Returns:
        dict with average_score, strengths, areas_to_improve, summary_feedback,
        recommendation, next_practice_suggestion, source.
    """
    # Compute a local average as fallback
    scores = [r.get("overall_score") for r in turn_results if r.get("overall_score") is not None]
    local_average = round(sum(scores) / len(scores), 1) if scores else None

    fallback = {
        "average_score": local_average,
        "summary_feedback": "You completed the pronunciation practice session. Keep listening and repeating to build clarity.",
        "strengths": ["You completed all practice items.", "You submitted clear recordings."],
        "areas_to_improve": ["Focus on word endings.", "Practise slower speech for difficult words."],
        "recommendation": "Practise daily with the sentence mode to improve fluency and word clarity.",
        "next_practice_suggestion": "Try a slightly harder difficulty and focus on multisyllable words.",
        "source": "fallback",
    }

    if not turn_results:
        return fallback

    turns_text = "\n\n".join(
        f"Q{r.get('turn_number', i + 1)}: {r.get('reference_text', '')}\n"
        f"Recognised: {r.get('recognised_text', '')}\n"
        f"Score: {r.get('overall_score', 'N/A')}/10"
        for i, r in enumerate(turn_results)
    )
    system_prompt = (
        "You are a friendly pronunciation coach writing a short end-of-session summary for a student. "
        "Return STRICT JSON only: "
        '{"summary_feedback":"...","strengths":["..."],"areas_to_improve":["..."],'
        '"recommendation":"...","next_practice_suggestion":"..."}'
    )
    user_prompt = (
        f"Difficulty: {difficulty}. Mode: pronunciation practice.\n"
        f"Full session:\n{turns_text}\n\n"
        "Write a short overall summary, 2 to 4 strengths, 2 to 4 practical areas to improve, "
        "one final teacher recommendation and one next practice suggestion. "
        "Base everything on the actual results shown. Do not invent scores."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.5, operation="pronunciation.session_summary", module="pronunciation", service="groq_pronunciation.summarize_pronunciation_session"))
    except Exception:
        data = {}

    if not isinstance(data, dict) or not data.get("summary_feedback"):
        return fallback

    return {
        "average_score": local_average,
        "summary_feedback": data.get("summary_feedback") or fallback["summary_feedback"],
        "strengths": data.get("strengths") if isinstance(data.get("strengths"), list) else fallback["strengths"],
        "areas_to_improve": data.get("areas_to_improve") if isinstance(data.get("areas_to_improve"), list) else fallback["areas_to_improve"],
        "recommendation": data.get("recommendation") or fallback["recommendation"],
        "next_practice_suggestion": data.get("next_practice_suggestion") or fallback["next_practice_suggestion"],
        "source": "groq",
    }


def generate_phonetic_hints(words):
    """Priority 3: Lightweight IPA / Phonetic-Level Feedback"""
    if not words:
        return []
        
    system_prompt = (
        "You are an English pronunciation assistant. For each word provided, return its IPA transcription "
        "and a one-line plain-English pronunciation tip.\n"
        "Return STRICT JSON only, matching this structure:\n"
        '[\n'
        '  {"word": "through", "ipa": "/θruː/", "tip": "Start with your tongue between your teeth for the \'th\', then a smooth \'roo\' sound."}\n'
        ']'
    )
    user_prompt = f"Words: {json.dumps(words)}"
    
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.3, operation="pronunciation.phonetic_hint_generation", module="pronunciation", service="groq_pronunciation.generate_phonetic_hints"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

