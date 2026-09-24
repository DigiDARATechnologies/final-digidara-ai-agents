import logging
import re

from .groq_common import _chat, _clamp_score, _extract_json, _score_average

logger = logging.getLogger(__name__)


def _fallback_writing_prompt(mode, difficulty, topic_title=None, topic_description=None):
    topic_context = (topic_title or topic_description or "your selected topic").strip().rstrip(".?!")
    if mode == "topic":
        prompts = {
            "easy": f"Write 5 to 8 simple sentences about {topic_context}.",
            "medium": f"Explain your thoughts about {topic_context} and include one clear example.",
            "hard": f"Analyze {topic_context} with a clear opinion, supporting reasons, and a brief conclusion.",
        }
    else:
        prompts = {
            "easy": "Write a short reply about this everyday situation.",
            "medium": "Describe what you would do in this everyday situation and explain why.",
            "hard": "Write a thoughtful response to this everyday situation, including your reasoning and possible outcome.",
        }
    return prompts.get(difficulty, prompts["medium"])


def generate_writing_prompt(mode, difficulty, topic_title, turn_number, history, topic_description=None):
    if mode == "topic":
        focus = (
            f"The topic is: \"{topic_title}\". Instruction: {topic_description or 'Use the selected topic title as the scope.'} "
            "Ask a writing question that helps the student explain this topic clearly."
        )
    else:
        focus = (
            f"This is everyday casual written conversation practice. Situation: \"{topic_title or 'Daily writing'}\". "
            f"Instruction: {topic_description or 'Ask a natural everyday writing question.'}"
        )

    difficulty_rules = {
        "easy": (
            "EASY STYLE: Write exactly one short, direct sentence. "
            "Ask only one thing. Use everyday words and simple grammar. "
            "Maximum 15 to 18 words total. "
            "Do not use compound, nested, conditional, or multi-clause sentences. "
            "Do not mention the student's struggles or previous mistakes. "
            "Example style: What do you like to do on a spring day?"
        ),
        "medium": (
            "MEDIUM STYLE: Write one clear sentence or two very short related sentences. "
            "Ask one main thing. Use familiar school, work, or daily vocabulary. "
            "Maximum 20 to 28 words total. "
            "Avoid long explanations, nested clauses, and rhetorical setup. "
            "Example style: Describe one activity you enjoy in spring and explain why."
        ),
        "hard": (
            "HARD STYLE: Write one focused prompt. You may include up to two related parts. "
            "Use richer vocabulary and more nuanced framing, but keep the grammar clean. "
            "Avoid rambling, preambles, and overly long setup. "
            "Maximum 35 to 45 words total."
        ),
    }
    style_rule = difficulty_rules.get(difficulty, difficulty_rules["easy"])

    history_text = "\n".join(
        f"Q{i+1}: {h['question']}\nA{i+1}: {h['answer']}" for i, h in enumerate(history)
    ) or "This is the first prompt of the session."

    system_prompt = (
        "You are a plain-English writing coach for students practising English. "
        "Generate only the next writing prompt. Keep it short, single-focus, and appropriate for the selected difficulty. "
        "Never include preamble, feedback, meta-commentary, or phrases like 'It seems like you are having trouble'. "
        "Do not analyze the student's ability. Do not ask several sub-questions at once. Go straight to the question or writing task. "
        "The same style rules apply to every turn, including follow-up prompts."
    )
    user_prompt = (
        f"Difficulty: {difficulty}.\n"
        f"{style_rule}\n\n"
        f"{focus}\n\n"
        f"So far:\n{history_text}\n\n"
        f"This is prompt number {turn_number}. "
        "Reply with ONLY the next student-facing writing prompt. "
        "No labels, no preamble, no feedback, no markdown."
    )
    try:
        prompt = _chat(system_prompt, user_prompt, temperature=0.7, operation="writing.daily_challenge_generation" if mode == "daily" else "writing.prompt_generation", module="writing", service="groq_writing.generate_writing_prompt")
    except Exception:
        return _fallback_writing_prompt(mode, difficulty, topic_title, topic_description)
    return prompt.strip().strip('"') or _fallback_writing_prompt(mode, difficulty, topic_title, topic_description)


def generate_writing_chat_reply(topic, difficulty, history=None):
    """Create one short, contextual reply for the optional Writing chat mode."""
    topic = (topic or "this topic").strip()
    clean_history = [item for item in (history or []) if isinstance(item, dict)][-6:]
    history_text = "\n".join(
        f"{'Student' if item.get('role') == 'user' else 'Coach'}: {str(item.get('text') or '').strip()}"
        for item in clean_history if str(item.get("text") or "").strip()
    ) or "This is the first message."
    fallback = {
        "reply": (
            f"That's an interesting topic! What do you already know about {topic}?"
            if not clean_history else "That's a good start! Can you give me one example from everyday life?"
        ),
        "corrected_answer": None,
    }
    system_prompt = (
        "You are a warm English conversation partner helping a student discuss one writing topic. "
        "Reply naturally in one or two short sentences, acknowledge something specific from the latest student message, "
        "then ask exactly one related follow-up question. Also give one corrected_answer only if the latest student message "
        "has a clear grammar or phrasing error. Preserve meaning. Return strict JSON only: "
        '{"reaction":"friendly acknowledgment","next_question":"one related follow-up question","corrected_answer":"corrected sentence or null"}. '
        "Do not score, write a long lesson, or use markdown."
    )
    user_prompt = (
        f"Topic: {topic}\nDifficulty: {difficulty}\nConversation:\n{history_text}\n\n"
        "Return only the JSON object."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.65, operation="writing.chat_reply", module="writing", service="groq_writing.generate_writing_chat_reply"))
        if not isinstance(data, dict):
            return fallback
        reaction = str(data.get("reaction") or "").strip()
        next_question = str(data.get("next_question") or "").strip()
        reply = " ".join(part for part in (reaction, next_question) if part)
        corrected_answer = str(data.get("corrected_answer") or "").strip() or None
        return {"reply": reply or fallback["reply"], "reaction": reaction, "next_question": next_question, "corrected_answer": corrected_answer}
    except Exception:
        return fallback


def _estimate_live_grade(text, issue_count):
    words = len(re.findall(r"\b\w+\b", text or ""))
    if words < 8:
        return None
    base = 8.5
    if words < 20:
        base -= 0.5
    base -= min(issue_count, 5) * 0.7
    return max(1, min(10, round(base, 1)))


def _fallback_live_issues(text):
    rules = [
        (r"(?<![A-Za-z])i(?![A-Za-z])", "grammar", "Capitalize the pronoun 'I'.", "I"),
        (r"\b[Ii]\s+has\b", "grammar", "Use 'have' with I.", "I have"),
        (r"\b[Ss]he\s+go\b", "grammar", "Use the -s form after she.", "She goes"),
        (r"\b[Hh]e\s+go\b", "grammar", "Use the -s form after he.", "He goes"),
        (r"\b[Dd]on't\s+likes\b", "grammar", "Use the base verb after don't.", "don't like"),
        (r"\b[Rr]ecieve\b", "grammar", "Correct the spelling of 'receive'.", "receive"),
        (r"(?m)(^|[.!?]\s+)([a-z])", "grammar", "Capitalize the first word of the sentence.", None),
        (r"\b[Vv]ery very\b", "clarity", "Avoid repeating 'very'.", "very"),
        (r"\b[aA]\s+apple\b", "grammar", "Use 'an' before a vowel sound.", "an apple"),
    ]
    issues = []
    for pattern, issue_type, explanation, suggestion in rules:
        for match in re.finditer(pattern, text or ""):
            if suggestion is None:
                start = match.start(2)
                end = match.end(2)
                replacement = match.group(2).upper()
            else:
                start = match.start()
                end = match.end()
                replacement = suggestion
            if any(start < issue["end"] and end > issue["start"] for issue in issues):
                continue
            issues.append({
                "start": start,
                "end": end,
                "text": text[start:end],
                "type": issue_type,
                "explanation": explanation,
                "suggestion": replacement,
            })
            if len(issues) >= 5:
                return issues
    return issues


def _normalize_live_issues(data, text):
    if isinstance(data, list):
        raw_issues = data
    elif isinstance(data, dict):
        raw_issues = data.get("issues") or data.get("flagged_spans") or data.get("spans") or []
    else:
        raw_issues = []
    if not isinstance(raw_issues, list):
        raw_issues = []
    normalized = []
    used_ranges = set()
    for item in raw_issues[:6]:
        if not isinstance(item, dict):
            continue
        issue_type = str(item.get("type") or "grammar").strip().lower()
        if issue_type not in {"grammar", "clarity"}:
            issue_type = "grammar"
        suggestion = str(item.get("suggestion") or item.get("replacement") or "").strip()
        explanation = str(item.get("explanation") or "Try this clearer version.").strip()
        phrase = str(item.get("text") or item.get("phrase") or item.get("matched_text") or "").strip()
        try:
            start = int(item.get("start"))
            end = int(item.get("end"))
        except (TypeError, ValueError):
            start = -1
            end = -1
        if start < 0 or end <= start or end > len(text) or (phrase and text[start:end] != phrase):
            if not phrase:
                continue
            start = text.lower().find(phrase.lower())
            end = start + len(phrase) if start >= 0 else -1
        if start < 0 or end <= start or end > len(text) or not suggestion:
            continue
        key = (start, end)
        if key in used_ranges:
            continue
        used_ranges.add(key)
        normalized.append({
            "start": start,
            "end": end,
            "text": text[start:end],
            "type": issue_type,
            "explanation": explanation[:180],
            "suggestion": suggestion[:180],
        })
    return sorted(normalized, key=lambda issue: (issue["start"], issue["end"]))[:5]


def live_writing_check(text, difficulty="easy", mode="topic", prompt=""):
    text = (text or "")[:2500]
    if len(text.strip()) < 8:
        return {"issues": [], "grade": None, "source": "fallback"}

    fallback_issues = _fallback_live_issues(text)
    fallback = {
        "issues": fallback_issues,
        "grade": _estimate_live_grade(text, len(fallback_issues)),
        "source": "fallback",
    }
    system_prompt = (
        "You are a fast live writing correction coach. Return STRICT JSON only. "
        "Flag only clear grammar or clarity problems in the student's draft. "
        "Do not evaluate the full answer and do not rewrite whole sentences."
    )
    user_prompt = (
        f"Mode: {mode}. Difficulty: {difficulty}. Prompt: {prompt or 'N/A'}\n\n"
        f"Draft text:\n{text}\n\n"
        "Return this JSON shape only: "
        '{"issues":[{"start":0,"end":4,"text":"span","type":"grammar","explanation":"short reason","suggestion":"replacement"}],'
        '"grade":7.0}\n'
        "Rules: start/end are zero-based character offsets in the exact draft text. "
        "Use type grammar for correctness, clarity for unclear wording. "
        "Return at most 5 issues. Suggest replacements only for the flagged span."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.1, max_tokens=550, operation="writing.grammar_correction", module="writing", service="groq_writing.live_writing_check"))
    except Exception:
        logger.exception("Live writing evaluation failed; using fallback feedback")
        return fallback
    model_issues = _normalize_live_issues(data, text)
    issues = [*fallback_issues]
    for issue in model_issues:
        if any(issue["start"] < existing["end"] and issue["end"] > existing["start"] for existing in issues):
            continue
        issues.append(issue)
        if len(issues) >= 5:
            break
    try:
        grade = float(data.get("grade")) if isinstance(data, dict) else _estimate_live_grade(text, len(issues))
    except (TypeError, ValueError, AttributeError):
        grade = _estimate_live_grade(text, len(issues))
    return {
        "issues": issues,
        "grade": max(1, min(10, round(grade, 1))) if grade is not None else None,
        "source": "groq" if issues or isinstance(data, dict) else "fallback",
    }


def live_writing_insights(text, difficulty="easy", mode="topic", prompt="", is_duplicate=False):
    """Return grammar issues and tone in one Groq request plus local duplicate state."""
    text = (text or "")[:2500]
    fallback_issues = _fallback_live_issues(text)
    fallback = {
        "issues": fallback_issues,
        "grade": _estimate_live_grade(text, len(fallback_issues)),
        "tone": "neutral",
        "confidence": 0.0,
        "is_duplicate": bool(is_duplicate),
        "source": "fallback",
    }
    if len(text.strip()) < 8:
        return fallback

    system_prompt = (
        "You are a fast writing coach. Return STRICT JSON only with issues and tone. "
        "Flag only clear grammar or clarity problems. Use character offsets for each issue. "
        "Schema: {\"issues\":[{\"start\":0,\"end\":1,\"text\":\"...\",\"suggestion\":\"...\",\"type\":\"grammar\",\"explanation\":\"...\"}],"
        "\"tone\":\"confident|formal|casual|hesitant|neutral|enthusiastic|polite\",\"confidence\":0.0}."
    )
    user_prompt = (
        f"Mode: {mode}. Difficulty: {difficulty}. Prompt: {prompt[:500]}\n"
        f"Check this student writing and classify its primary tone:\n\n{text}"
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.1, max_tokens=650, operation="writing.grammar_correction", module="writing", service="groq_writing.live_writing_insights"))
    except Exception:
        logger.exception("Live writing insights failed; using fallback feedback")
        return fallback

    model_issues = _normalize_live_issues(data.get("issues", []) if isinstance(data, dict) else [], text)
    issues = [*fallback_issues]
    for issue in model_issues:
        if any(issue["start"] < existing["end"] and issue["end"] > existing["start"] for existing in issues):
            continue
        issues.append(issue)
    issues = issues[:6]
    tone = str(data.get("tone") or "neutral").strip().lower() if isinstance(data, dict) else "neutral"
    allowed_tones = {"confident", "formal", "casual", "hesitant", "neutral", "enthusiastic", "polite"}
    if tone not in allowed_tones:
        tone = "neutral"
    return {
        "issues": issues,
        "grade": _estimate_live_grade(text, len(issues)),
        "tone": tone,
        "confidence": float(data.get("confidence") or 0.0) if isinstance(data, dict) else 0.0,
        "is_duplicate": bool(is_duplicate),
        "source": "groq" if isinstance(data, dict) else "fallback",
    }


def evaluate_writing_answer(mode, difficulty, topic_title, question, answer):
    knowledge_instruction = (
        "Also score 'knowledge' (0.0-10.0): how accurate and knowledgeable the writing is about the topic."
        if mode == "topic"
        else "Set 'knowledge' to null. Also score 'relevance' (0.0-10.0) for how well the answer responds to the daily prompt."
    )
    system_prompt = (
        "You are an expert writing evaluator. Respond with STRICT JSON only, no markdown fences. "
        "Focus on grammar, clarity, spelling, and vocabulary. "
        "When giving grammar corrections in the top-level 'mistake_points' array, you MUST extract the EXACT original phrase "
        "from the user's submitted text and show the EXACT corrected version — never output placeholder text, ellipsis (...), or generic symbols.\n"
        "Format each correction as exactly:\n"
        "\"<exact original phrase from user's text>\" → \"<corrected phrase>\" — <short reason why>\n"
        "Example (always replace with the user's actual words):\n"
        "\"me and him went to the store\" → \"he and I went to the store\" — subject pronoun order and case correction\n"
        "If there are no grammar errors to correct, the array must contain exactly one string: \"No grammar corrections needed for this response.\" "
        "Do NOT output empty quotes or ellipsis under any circumstance. Every correction must reference text that actually appears in the user's submitted answer — do not invent or generalize corrections. "
        "Preserve the student's original meaning in corrected_answer. "
        "matching this schema exactly:\n"
        '{"appreciation":"Good attempt.","status":"Needs Improvement","original_answer":"...",'
        '"corrected_answer":"...","better_natural_answer":"...","explanation":"...",'
        '"mistake_points":["\"incorrect phrase\" → \"corrected phrase\" — reason"],'
        '"mistakes":[{"incorrect":"...","correct":"...",'
        '"type":"Grammar","mistake_points":["short bullet"],"explanation":"..."}],'
        '"vocabulary_suggestions":[{"original":"...","suggestion":"...","example":"..."}],'
        '"strengths":["..."],"areas_to_improve":["..."],'
        '"short_feedback":"...","scores":{"grammar":0.0,"vocabulary":0.0,"clarity":0.0,'
        '"spelling":0.0,"relevance":0.0,"knowledge":0.0,"overall":0.0}}'
    )
    user_prompt = (
        f"Difficulty: {difficulty}. Mode: {mode}. Topic: {topic_title or 'N/A'}.\n"
        f"Prompt given: {question}\n"
        f"Student's written answer: {answer}\n\n"
        f"Classify status as Correct, Mostly Correct, Partially Correct, Needs Improvement, Off Topic, or No Answer. "
        f"Score grammar, vocabulary, clarity, spelling, and overall from 0.0 to 10.0. {knowledge_instruction} "
        f"Give a corrected answer and up to six distinct grammar corrections. Do not score above 10. "
        f"Avoid long grammar lessons, generic praise, a next question, or any follow-up task."
    )
    try:
        raw = _chat(system_prompt, user_prompt, temperature=0.3, operation="writing.answer_evaluation", module="writing", service="groq_writing.evaluate_writing_answer")
        data = _extract_json(raw)
    except Exception:
        logger.exception("Writing answer AI evaluation failed; using fallback feedback")
        data = {}
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else data
    normalized_scores = {
        "grammar": _clamp_score(scores.get("grammar")),
        "vocabulary": _clamp_score(scores.get("vocabulary")),
        "clarity": _clamp_score(scores.get("clarity")),
        "spelling": _clamp_score(scores.get("spelling")),
        "relevance": _clamp_score(scores.get("relevance")) if mode != "topic" else None,
        "knowledge": _clamp_score(scores.get("knowledge")) if mode == "topic" else None,
    }
    normalized_scores["overall"] = _clamp_score(scores.get("overall") or _score_average(normalized_scores.values()))
    def _normalize_points(value):
        if isinstance(value, list):
            points = [str(item).strip() for item in value if str(item or "").strip()]
            return points[:4]
        if isinstance(value, str):
            point = value.strip()
            return [point] if point else []
        return []

    mistakes = data.get("mistakes") if isinstance(data.get("mistakes"), list) else []
    normalized_mistakes = []
    for mistake in mistakes[:4]:
        if not isinstance(mistake, dict):
            continue
        normalized_mistakes.append({
            **mistake,
            "explanation": str(mistake.get("explanation") or mistake.get("mistake_explanation") or "").strip(),
            "mistake_points": _normalize_points(mistake.get("mistake_points") or mistake.get("points")),
        })
    vocabulary = data.get("vocabulary_suggestions") if isinstance(data.get("vocabulary_suggestions"), list) else []
    strengths = data.get("strengths") if isinstance(data.get("strengths"), list) else []
    areas = data.get("areas_to_improve") if isinstance(data.get("areas_to_improve"), list) else []
    mistake_points = _normalize_points(data.get("mistake_points") or data.get("mistake_explanation_points"))
    if not mistake_points and normalized_mistakes:
        mistake_points = [point for mistake in normalized_mistakes for point in mistake.get("mistake_points", [])][:4]
    return {
        "appreciation": data.get("appreciation") or "Good attempt.",
        "status": data.get("status") or ("No Answer" if not answer.strip() else "Partially Correct"),
        "original_answer": answer,
        "corrected_answer": data.get("corrected_answer") or answer,
        "explanation": data.get("explanation") or data.get("mistake_explanation") or "A detailed correction was not available for this answer.",
        "mistake_points": mistake_points,
        "mistakes": normalized_mistakes[:4],
        "vocabulary_suggestions": vocabulary[:3],
        "strengths": strengths[:4] or ["You submitted a complete response."],
        "areas_to_improve": areas[:4] or ["Add one clear supporting detail and review grammar before submitting."],
        "better_natural_answer": data.get("better_natural_answer") or data.get("corrected_answer") or answer,
        "short_feedback": data.get("short_feedback") or data.get("feedback") or "Your answer was received. Keep writing in complete sentences.",
        "feedback": data.get("short_feedback") or data.get("feedback") or "Your answer was received. Keep writing in complete sentences.",
        "scores": normalized_scores,
        "grammar": normalized_scores["grammar"],
        "vocabulary": normalized_scores["vocabulary"],
        "clarity": normalized_scores["clarity"],
        "spelling": normalized_scores["spelling"],
        "relevance": normalized_scores["relevance"],
        "knowledge": normalized_scores["knowledge"],
        "overall": normalized_scores["overall"],
    }


def generate_writing_hint(mode, difficulty, topic_title, topic_description, question, answer, hint_count):
    fallback = {
        "outline": [
            "Start with a direct answer to the prompt.",
            "Add one reason or example.",
            "Close with a clear final sentence.",
        ],
        "useful_words": ["because", "for example", "however"],
        "transition_words": ["first", "also", "finally"],
        "teacher_tip": "Use your own ideas. The hint is a plan, not a full answer.",
        "source": "fallback",
    }
    system_prompt = (
        "You are a writing coach giving a small hint before a student submits. "
        "Return STRICT JSON only and never write the student's full answer."
    )
    user_prompt = (
        f"Mode: {mode}. Difficulty: {difficulty}. Topic: {topic_title or 'Daily writing'}.\n"
        f"Topic instruction: {topic_description or 'N/A'}\nPrompt: {question}\n"
        f"Student draft so far: {answer or '(empty)'}\nHint number: {hint_count + 1} of 2.\n\n"
        "Return this JSON shape: "
        '{"outline":["..."],"useful_words":["..."],"transition_words":["..."],"teacher_tip":"..."} '
        "Keep it concise. Give structure, vocabulary and transitions only; do not compose a full response."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.45, operation="writing.inspiration_hint", module="writing", service="groq_writing.generate_writing_hint"))
    except Exception:
        logger.exception("Sentence rewrite AI evaluation failed; using fallback feedback")
        data = {}
    if not isinstance(data, dict):
        return fallback
    return {
        "outline": data.get("outline")[:4] if isinstance(data.get("outline"), list) else fallback["outline"],
        "useful_words": data.get("useful_words")[:6] if isinstance(data.get("useful_words"), list) else fallback["useful_words"],
        "transition_words": data.get("transition_words")[:6] if isinstance(data.get("transition_words"), list) else fallback["transition_words"],
        "teacher_tip": str(data.get("teacher_tip") or fallback["teacher_tip"]).strip()[:240],
        "source": "groq",
    }


REWRITE_FALLBACK_SENTENCES = {
    "easy": [
        "She go to school every day.",
        "I am very happy to meet you yesterday.",
        "He don't like coffee.",
    ],
    "medium": [
        "I am very much interested to join in your company.",
        "The meeting was discussed about the new project.",
        "Please explain me the process for applying this course.",
    ],
    "hard": [
        "Despite of the challenges, the team were able to completed the project on time.",
        "The proposal aims to improve communication between departments by ensuring informations are shared clearly.",
        "Had I knew about the deadline earlier, I would have submitted the report more professionally.",
    ],
}


def generate_sentence_rewrite_prompt(difficulty):
    fallback = REWRITE_FALLBACK_SENTENCES.get(difficulty, REWRITE_FALLBACK_SENTENCES["medium"])[0]
    system_prompt = (
        "You are a friendly English writing teacher. Generate one short sentence with grammar, word choice, "
        "or sentence-structure problems. The learner must rewrite it correctly."
    )
    user_prompt = (
        f"Difficulty: {difficulty}. Return STRICT JSON only with this schema: "
        '{"sentence":"...","focus":"Grammar, clarity, and natural expression","teacher_hint":"..."} '
        "Use a realistic communication sentence. Do not include the corrected answer."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.7, operation="writing.natural_rewrite", module="writing", service="groq_writing.generate_sentence_rewrite_prompt"))
    except Exception:
        data = {}
    return {
        "sentence": str(data.get("sentence") or fallback).strip()[:500],
        "focus": str(data.get("focus") or "Grammar, clarity, and natural expression").strip()[:160],
        "teacher_hint": str(data.get("teacher_hint") or "Rewrite the sentence so it sounds clear, correct, and natural.").strip()[:220],
        "source": "groq" if data else "fallback",
    }


def evaluate_sentence_rewrite(difficulty, original_sentence, student_rewrite):
    system_prompt = (
        "You are an AI English writing teacher. Evaluate a student's rewritten sentence. "
        "Respond with STRICT JSON only, no markdown fences, matching this schema exactly:\n"
        '{"appreciation":"Good attempt.","status":"Needs Improvement","corrected_answer":"...",'
        '"better_natural_answer":"...","explanation":"...","teacher_tip":"...",'
        '"mistakes":[{"incorrect":"...","correct":"...","type":"Grammar","explanation":"..."}],'
        '"vocabulary_suggestions":[{"original":"...","suggestion":"...","example":"..."}],'
        '"short_feedback":"...","scores":{"grammar":0,"vocabulary":0,"clarity":0,"naturalness":0,"overall":0}}'
    )
    user_prompt = (
        f"Difficulty: {difficulty}.\nOriginal sentence: {original_sentence}\nStudent rewrite: {student_rewrite}\n\n"
        "Check whether the rewrite fixes the original sentence and sounds natural. Score grammar, vocabulary, "
        "clarity, naturalness, and overall from 0 to 100. Give simple teacher feedback."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.25, operation="writing.natural_rewrite", module="writing", service="groq_writing.evaluate_sentence_rewrite"))
    except Exception:
        data = {}
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    normalized_scores = {
        "grammar": _clamp_score(scores.get("grammar")),
        "vocabulary": _clamp_score(scores.get("vocabulary")),
        "clarity": _clamp_score(scores.get("clarity")),
        "naturalness": _clamp_score(scores.get("naturalness")),
    }
    normalized_scores["overall"] = _clamp_score(scores.get("overall") or _score_average(normalized_scores.values()))
    corrected = data.get("corrected_answer") or student_rewrite
    mistakes = data.get("mistakes") if isinstance(data.get("mistakes"), list) else []
    vocabulary = data.get("vocabulary_suggestions") if isinstance(data.get("vocabulary_suggestions"), list) else []
    return {
        "appreciation": data.get("appreciation") or "Good attempt.",
        "status": data.get("status") or ("No Answer" if not student_rewrite.strip() else "Partially Correct"),
        "original_sentence": original_sentence,
        "student_rewrite": student_rewrite,
        "corrected_answer": corrected,
        "better_natural_answer": data.get("better_natural_answer") or corrected,
        "explanation": data.get("explanation") or "Compare your rewrite with the corrected version and check grammar, word order, and natural phrasing.",
        "teacher_tip": data.get("teacher_tip") or "Read the corrected sentence aloud and notice the smoother structure.",
        "mistakes": mistakes[:4],
        "vocabulary_suggestions": vocabulary[:3],
        "short_feedback": data.get("short_feedback") or data.get("feedback") or "Your rewrite was checked by the AI teacher.",
        "scores": normalized_scores,
        "source": "groq" if data else "fallback",
    }


def summarize_writing_session(mode, topic_title, turns):
    turns_text = "\n\n".join(
        f"Q{t['turn_number']}: {t['ai_prompt']}\nA{t['turn_number']}: {t['user_response']}"
        for t in turns
    )
    system_prompt = (
        "You are a writing coach writing a short end-of-session summary for a student. "
        "Return STRICT JSON only: "
        '{"summary_feedback":"...","strengths":["..."],"areas_to_improve":["..."],'
        '"common_mistakes":[{"type":"...","example":"...","correction":"..."}],'
        '"recommendation":"...","next_practice_suggestion":"..."}'
    )
    user_prompt = (
        f"Mode: {mode}. Topic: {topic_title or 'Daily writing'}.\n"
        f"Full session:\n{turns_text}\n\n"
        "Write a short overall summary, 2 to 5 strengths, 2 to 5 practical areas to improve, common mistakes, "
        "one final teacher recommendation and one next practice suggestion. Base everything on the actual answers."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.5, operation="writing.session_summary", module="writing", service="groq_writing.summarize_writing_session"))
    except Exception:
        data = {}
    return {
        "summary_feedback": data.get("summary_feedback") or "You completed the writing practice. Keep using complete sentences and clear structure.",
        "strengths": data.get("strengths") if isinstance(data.get("strengths"), list) else ["You answered the prompts.", "You communicated your main ideas."],
        "areas_to_improve": data.get("areas_to_improve") if isinstance(data.get("areas_to_improve"), list) else ["Check grammar before submitting.", "Add supporting details."],
        "common_mistakes": data.get("common_mistakes") if isinstance(data.get("common_mistakes"), list) else [],
        "recommendation": data.get("recommendation") or "Practise writing short answers with one clear reason and one example.",
        "next_practice_suggestion": data.get("next_practice_suggestion") or "Write about a familiar daily situation.",
    }


REWRITE_FALLBACK_SENTENCES = {
    "easy": [
        "She go to school every day.",
        "I am very happy to meet you yesterday.",
        "He don't like coffee.",
    ],
    "medium": [
        "I am very much interested to join in your company.",
        "The meeting was discussed about the new project.",
        "Please explain me the process for applying this course.",
    ],
    "hard": [
        "Despite of the challenges, the team were able to completed the project on time.",
        "The proposal aims to improve communication between departments by ensuring informations are shared clearly.",
        "Had I knew about the deadline earlier, I would have submitted the report more professionally.",
    ],
}


def generate_sentence_rewrite_prompt(difficulty):
    fallback = REWRITE_FALLBACK_SENTENCES.get(difficulty, REWRITE_FALLBACK_SENTENCES["medium"])[0]
    system_prompt = (
        "You are a friendly English writing teacher. Generate one short sentence with grammar, word choice, "
        "or sentence-structure problems. The learner must rewrite it correctly."
    )
    user_prompt = (
        f"Difficulty: {difficulty}. Return STRICT JSON only with this schema: "
        '{"sentence":"...","focus":"Grammar, clarity, and natural expression","teacher_hint":"..."} '
        "Use a realistic communication sentence. Do not include the corrected answer."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.7, operation="writing.natural_rewrite", module="writing", service="groq_writing.generate_sentence_rewrite_prompt"))
    except Exception:
        data = {}
    return {
        "sentence": str(data.get("sentence") or fallback).strip()[:500],
        "focus": str(data.get("focus") or "Grammar, clarity, and natural expression").strip()[:160],
        "teacher_hint": str(data.get("teacher_hint") or "Rewrite the sentence so it sounds clear, correct, and natural.").strip()[:220],
        "source": "groq" if data else "fallback",
    }


def evaluate_sentence_rewrite(difficulty, original_sentence, student_rewrite):
    system_prompt = (
        "You are an AI English writing teacher. Evaluate a student's rewritten sentence. "
        "Respond with STRICT JSON only, no markdown fences, matching this schema exactly:\n"
        '{"appreciation":"Good attempt.","status":"Needs Improvement","corrected_answer":"...",'
        '"better_natural_answer":"...","explanation":"...","teacher_tip":"...",'
        '"mistakes":[{"incorrect":"...","correct":"...","type":"Grammar","explanation":"..."}],'
        '"vocabulary_suggestions":[{"original":"...","suggestion":"...","example":"..."}],'
        '"short_feedback":"...","scores":{"grammar":0,"vocabulary":0,"clarity":0,"naturalness":0,"overall":0}}'
    )
    user_prompt = (
        f"Difficulty: {difficulty}.\nOriginal sentence: {original_sentence}\nStudent rewrite: {student_rewrite}\n\n"
        "Check whether the rewrite fixes the original sentence and sounds natural. Score grammar, vocabulary, "
        "clarity, naturalness, and overall from 0 to 100. Give simple teacher feedback."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.25, operation="writing.natural_rewrite", module="writing", service="groq_writing.evaluate_sentence_rewrite"))
    except Exception:
        data = {}
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    normalized_scores = {
        "grammar": _clamp_score(scores.get("grammar")),
        "vocabulary": _clamp_score(scores.get("vocabulary")),
        "clarity": _clamp_score(scores.get("clarity")),
        "naturalness": _clamp_score(scores.get("naturalness")),
    }
    normalized_scores["overall"] = _clamp_score(scores.get("overall") or _score_average(normalized_scores.values()))
    corrected = data.get("corrected_answer") or student_rewrite
    mistakes = data.get("mistakes") if isinstance(data.get("mistakes"), list) else []
    vocabulary = data.get("vocabulary_suggestions") if isinstance(data.get("vocabulary_suggestions"), list) else []
    return {
        "appreciation": data.get("appreciation") or "Good attempt.",
        "status": data.get("status") or ("No Answer" if not student_rewrite.strip() else "Partially Correct"),
        "original_sentence": original_sentence,
        "student_rewrite": student_rewrite,
        "corrected_answer": corrected,
        "better_natural_answer": data.get("better_natural_answer") or corrected,
        "explanation": data.get("explanation") or "Compare your rewrite with the corrected version and check grammar, word order, and natural phrasing.",
        "teacher_tip": data.get("teacher_tip") or "Read the corrected sentence aloud and notice the smoother structure.",
        "mistakes": mistakes[:4],
        "vocabulary_suggestions": vocabulary[:3],
        "short_feedback": data.get("short_feedback") or data.get("feedback") or "Your rewrite was checked by the AI teacher.",
        "scores": normalized_scores,
        "source": "groq" if data else "fallback",
    }


def summarize_writing_session(mode, topic_title, turns):
    turns_text = "\n\n".join(
        f"Q{t['turn_number']}: {t['ai_prompt']}\nA{t['turn_number']}: {t['user_response']}"
        for t in turns
    )
    system_prompt = (
        "You are a writing coach writing a short end-of-session summary for a student. "
        "Return STRICT JSON only: "
        '{"summary_feedback":"...","strengths":["..."],"areas_to_improve":["..."],'
        '"common_mistakes":[{"type":"...","example":"...","correction":"..."}],'
        '"recommendation":"...","next_practice_suggestion":"..."}'
    )
    user_prompt = (
        f"Mode: {mode}. Topic: {topic_title or 'Daily writing'}.\n"
        f"Full session:\n{turns_text}\n\n"
        "Write a short overall summary, 2 to 5 strengths, 2 to 5 practical areas to improve, common mistakes, "
        "one final teacher recommendation and one next practice suggestion. Base everything on the actual answers."
    )
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.5, operation="writing.session_summary", module="writing", service="groq_writing.summarize_writing_session"))
    except Exception:
        data = {}
    return {
        "summary_feedback": data.get("summary_feedback") or "You completed the writing practice. Keep using complete sentences and clear structure.",
        "strengths": data.get("strengths") if isinstance(data.get("strengths"), list) else ["You answered the prompts.", "You communicated your main ideas."],
        "areas_to_improve": data.get("areas_to_improve") if isinstance(data.get("areas_to_improve"), list) else ["Check grammar before submitting.", "Add supporting details."],
        "common_mistakes": data.get("common_mistakes") if isinstance(data.get("common_mistakes"), list) else [],
        "recommendation": data.get("recommendation") or "Practise writing short answers with one clear reason and one example.",
        "next_practice_suggestion": data.get("next_practice_suggestion") or "Write about a familiar daily situation.",
    }


def quick_grammar_check(text):
    fallback = {"issues": [], "source": "fallback"}
    if not text or len(text.strip()) < 15:
        return fallback
    system_prompt = (
        "You are a fast grammar and spelling checker for student writing. "
        "Return STRICT JSON only with this schema: "
        '{"issues":[{"phrase":"...","suggestion":"...","type":"grammar"|"spelling"}]}. '
        "Report only the top 3 to 5 clear issues. Do not evaluate style, tone, or overall quality."
    )
    user_prompt = f"Check this text for quick grammar or spelling issues:\n\n{text[:1200]}"
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.1, max_tokens=220, operation="writing.grammar_correction", module="writing", service="groq_writing.quick_grammar_check"))
    except Exception:
        return fallback
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        return fallback
    issues = []
    for issue in data.get("issues", [])[:5]:
        if not isinstance(issue, dict):
            continue
        phrase = str(issue.get("phrase") or "").strip()
        suggestion = str(issue.get("suggestion") or "").strip()
        issue_type = str(issue.get("type") or "grammar").strip().lower()
        if issue_type not in {"grammar", "spelling"}:
            issue_type = "grammar"
        if phrase and suggestion:
            issues.append({
                "phrase": phrase[:120],
                "suggestion": suggestion[:160],
                "type": issue_type,
            })
    return {"issues": issues, "source": "groq"}


def detect_tone(text):
    fallback = {"tone": "neutral", "confidence": 0.0, "source": "fallback"}
    if not text or len(text.strip()) < 15:
        return fallback
    system_prompt = (
        "Classify the tone of the given text. Return STRICT JSON only: "
        '{"tone":"confident"|"formal"|"casual"|"hesitant"|"neutral"|"enthusiastic"|"polite","confidence":0.9}'
    )
    user_prompt = f"Detect the primary tone of this text:\n\n{text[:1000]}"
    try:
        data = _extract_json(_chat(system_prompt, user_prompt, temperature=0.1, max_tokens=100, operation="writing.tone_detection", module="writing", service="groq_writing.detect_tone"))
        if isinstance(data, dict) and "tone" in data:
            return {
                "tone": str(data.get("tone")).lower(),
                "confidence": float(data.get("confidence") or 0.8),
                "source": "groq"
            }
    except Exception:
        pass
    return fallback


