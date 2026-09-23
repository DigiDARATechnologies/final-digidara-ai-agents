"""Per-answer evaluation, ideal answers, and interview scorecards."""

import json

from .chat_client import json_object as _json_object
from .chat_client import score as _score


IDEAL_ANSWER_MAX_WORDS = {
    "beginner": 60,
    "intermediate": 90,
    "advanced": 120,
}

BEGINNER_TECHNICAL_RUBRIC = (
    "BEGINNER TECHNICAL RUBRIC: Judge whether the answer directly explains the basic "
    "concept in understandable language. Mark correct when the core idea is accurate, "
    "even if the answer is short and omits advanced details or exact terminology. "
    "Mark partial only for a missing important basic point or a minor conceptual mistake. "
    "Mark wrong for an incorrect, unrelated, or empty answer. Do not require internals, "
    "architecture, optimization, advanced REST constraints, or implementation details "
    "unless the beginner question itself explicitly asks for an essential basic detail. "
    "Keep feedback simple and educational; give an ideal answer of about 1-3 plain-language "
    "sentences focused on the core concept, without unnecessary advanced terminology. "
)

TECHNICAL_LEVEL_SCORING = {
    "beginner": (
        "BEGINNER SCORING: A clear one- or two-sentence explanation of the single basic "
        "concept is sufficient. Never require REST constraint lists, framework project internals, "
        "magic methods, optimization, architecture, or implementation details that the question "
        "did not ask for. Judge the actual question, including older questions that may be "
        "overly advanced for their label. "
    ),
    "intermediate": (
        "INTERMEDIATE SCORING: Expect accurate explanation of the named concept or pattern "
        "and a sensible common application or troubleshooting approach when requested. "
        "Do not require senior-level architecture, exhaustive constraint lists, or obscure edge cases. "
    ),
    "advanced": (
        "ADVANCED SCORING: When the question asks for design judgment, expect reasoned trade-offs, "
        "consequences, performance, security, reliability, or edge-case analysis as relevant. "
        "Credit defensible alternatives; do not require one preferred architecture or unasked details. "
    ),
}

HR_LEVEL_SCORING = {
    "beginner": (
        "BEGINNER HR SCORING: Credit a relevant, sincere, understandable answer to a simple "
        "introduction, motivation, or everyday situation. Education or personal examples count. "
        "Do not require formal work history, a STAR structure, or leadership-level judgment. "
    ),
    "intermediate": (
        "INTERMEDIATE HR SCORING: When a behavioral question requests an example, look for a "
        "relevant situation, the candidate's own action, and a result or learning. Accept an "
        "informal narrative; do not require advanced leadership experience or perfect STAR wording. "
    ),
    "advanced": (
        "ADVANCED HR SCORING: Evaluate judgment in ambiguous situations, ownership, conflict "
        "resolution or leadership, and awareness of consequences when the question asks for them. "
        "Credit plausible alternative decisions supported by clear reasoning. "
    ),
}


def _clip_sentence(text, max_words=30):
    """Keep generated scorecard text concise even if the model exceeds its limit."""
    cleaned = (text or "").strip()
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
    return " ".join(words[:max_words]).rstrip(",;:") + "..."


def _ideal_answer_guidance(difficulty, round_type="technical"):
    if round_type == "hr":
        level_guidance = {
            "beginner": (
                "Use two or three clear, conversational sentences. Give enough relevant detail "
                "to answer the question without making the response sound rehearsed."
            ),
            "intermediate": (
                "Use three or four connected, conversational sentences. When appropriate, include "
                "the candidate's action, reasoning, and result or lesson in a natural structure."
            ),
            "advanced": (
                "Use three to five focused, conversational sentences. When appropriate, demonstrate "
                "ownership, judgment, trade-offs, impact, and reflection without sounding scripted."
            ),
        }.get(
            difficulty,
            "Use two or three complete, focused sentences matched to the question's complexity.",
        )
        return (
            f"Write an interview-recommended HR answer at {difficulty} difficulty. "
            "It must sound like a strong candidate speaking naturally and genuinely, not a "
            "memorized corporate script. Answer the behavioral question directly and demonstrate "
            "an effective structure through natural prose. Use a realistic example when appropriate, "
            "which may come from work, education, projects, volunteering, clubs, or everyday "
            "responsibilities. Do not require buzzwords or explicitly label STAR sections. Do not "
            "copy weak behavior, errors, or unsupported claims from the candidate's response, and do "
            "not imply this is the only acceptable answer. Use complete conversational sentences, "
            "without headings, bullets, meta-commentary, or phrases such as 'the answer is'. "
            f"{level_guidance} Stay concise enough to say aloud."
        )

    if difficulty == "beginner":
        return (
            "Write like a well-prepared candidate speaking naturally, not a dictionary definition. "
            "Use one or two clear, complete sentences, or a third when needed. Directly explain "
            "the core concept in plain language and, if useful, one simple example. "
            "Do not add advanced terminology, special methods, framework or language internals, "
            "architecture, or implementation details unless the beginner question explicitly "
            "asks for them. Avoid code snippets and provide a complete explanatory answer rather "
            "than a clipped phrase."
        )

    level_guidance = {
        "intermediate": (
            "Use two or three connected sentences. Explain the concept and add a useful "
            "practical implication, comparison, or common usage detail. Aim for roughly "
            "40 to 75 words."
        ),
        "advanced": (
            "Use two to four focused sentences. Include relevant reasoning, trade-offs, "
            "edge cases, performance implications, or design context. Aim for roughly "
            "55 to 95 words."
        ),
    }.get(
        difficulty,
        "Use one or two complete, focused sentences matched to the question's complexity.",
    )
    return (
        f"Write an interview-recommended answer at {difficulty} difficulty. "
        "It must sound like a well-prepared candidate speaking naturally in an interview, "
        "not a dictionary definition, glossary entry, fragment, or textbook paragraph. "
        "Answer the question directly before adding supporting detail. Use accurate technical "
        "terminology naturally and demonstrate conceptual understanding. Add one useful "
        "implication, distinction, example, or piece of context when it strengthens the answer. "
        "Use complete conversational sentences, without headings, bullets, meta-commentary, "
        "or phrases such as 'the answer is'. Do not copy inaccuracies from the candidate's "
        "response. Stay focused and concise enough to say aloud. "
        f"{level_guidance} "
        "Even for a simple question, provide a complete explanatory answer rather than a "
        "clipped phrase. Do not add length merely to reach a word count."
    )


def evaluate_answer(
    question,
    answer,
    difficulty,
    round_type="technical",
    *,
    chat_fn,
):
    """Evaluate one answer without changing the planned question sequence."""
    ideal_answer_guidance = _ideal_answer_guidance(difficulty, round_type)
    beginner_final_rule = (
        "FINAL BEGINNER RULE: Keep the reason and ideal_answer focused on the basic concept. "
        "Do not mention internal special methods, protocol mechanics, or advanced details as "
        "improvements when a simple correct explanation is enough.\n\n"
        if round_type == "technical" and difficulty == "beginner" else ""
    )
    if round_type == "hr":
        system_prompt = (
            "You are an accurate, supportive evaluator judging one SPOKEN HR or behavioral answer "
            f"at difficulty ({difficulty}). Evaluate the candidate's final meaning and substance. Do not "
            "evaluate accent, speech fluency, corporate polish, memorized phrasing, or use of business "
            "buzzwords.\n\n"
            "SPOKEN-ANSWER RULES: Ignore filler, hesitation, repetition, rambling, "
            "false starts, and phrases such as 'um', 'sorry', or 'I mean'. When the candidate self-corrects, judge the final meaning and do not penalize the withdrawn "
            "statement. Reconstruct the answer from the complete transcript; judge the final corrected meaning and do not grade "
            "isolated awkward phrases when the overall intended meaning is clear. Accept casual, "
            "simple, or informal language when it communicates a relevant and understandable answer.\n\n"
            "HR AND BEHAVIORAL RULES: Judge whether the candidate answered the question asked with "
            "relevant, genuine, on-topic information. Do not require corporate buzzwords, a memorized "
            "script, perfect STAR formatting, or artificially confident language. For introductory "
            "or motivation questions, look for relevant background, interests, goals, or reasons "
            "connected to the role. For experience or scenario questions, look for enough context to "
            "understand the situation, what the candidate personally did or would do, and the result, "
            "reasoning, or lesson when relevant. A valid example may come from employment, education, "
            "projects, volunteering, clubs, or everyday responsibilities. Do not penalize candidates "
            "for limited formal work experience when their example demonstrates the requested behavior. "
            "Evaluate the quality of the behavior or judgment described; do not mark an answer correct "
            "merely because it sounds polished. Do not invent experience, motives, actions, or results "
            "the candidate did not communicate.\n\n"
            'VERDICTS: Use exactly one verdict. "correct" when the final answer is relevant, '
            "understandable, and sufficiently addresses the behavioral intent. Minor rambling, simple "
            'language, imperfect structure, and omitted optional detail must remain "correct". '
            '"partial" only when relevant and credible substance is present but a material part needed '
            "to answer the question is genuinely missing or unclear, such as describing a conflict "
            "without explaining the candidate's own action. "
            '"wrong" only when the answer is off-topic, provides no meaningful answer, contradicts the '
            "question's premise without addressing it, or describes clearly unsuitable behavior without "
            "relevant reflection or correction. Never use wrong only because an answer lacks polish or "
            "corporate vocabulary.\n\n"
            "For the reason field: write one encouraging, constructive, specific sentence of at most "
            "25 words. Acknowledge useful content first whenever present, then identify the most important "
            "missing element or improvement. Never criticize speech style or personality.\n\n"
            f"For the ideal_answer field: {ideal_answer_guidance} Always provide it regardless of verdict.\n\n"
            "Respond ONLY with valid JSON in this exact shape:\n"
            "{\n"
            '  "verdict": "correct" | "partial" | "wrong",\n'
            '  "reason": "<encouraging, specific sentence, max 25 words>",\n'
            '  "ideal_answer": "<natural HR interview-recommended answer>"\n'
            "}"
        )
    else:
        terminology_reason = (
            "mention the precise term in the reason only if it is basic vocabulary useful for "
            "this difficulty; never add advanced mechanics. "
            if difficulty == "beginner" else "mention the precise term in the reason. "
        )
        terminology_refinement = (
            'keep the verdict "correct" and offer the precise term as a helpful refinement only '
            "when it is a simple beginner-level term; otherwise just affirm the correct idea. "
            if difficulty == "beginner" else
            'keep the verdict "correct" and offer the precise term as a helpful refinement. '
        )
        system_prompt = (
            "You are a friendly but accurate interview evaluator judging one SPOKEN answer "
            f"at difficulty ({difficulty}). "
            f"{BEGINNER_TECHNICAL_RUBRIC if difficulty == 'beginner' else ''}"
            "Evaluate the candidate's conceptual "
            "understanding and final corrected meaning, not speech fluency, polish, or ability "
            "to use exact textbook vocabulary. Ignore filler words, hesitation, "
            "repetition, rambling, false starts, and phrases such as 'um', 'sorry', or 'I mean'. "
            "When the candidate self-corrects, judge the final meaning and do not penalize "
            "an earlier statement they clearly withdrew. Accept casual language, approximate terminology, "
            "analogies, and non-technical wording when they communicate the correct concept. Do not lower "
            "a verdict merely because a precise term was omitted or replaced with an informal word; gently "
            f"{terminology_reason}Judge only what the original question asks. Do not "
            "require an example, implementation detail, edge case, or extra depth unless explicitly "
            "requested or essential to the core concept. Calibrate completeness to the stated difficulty; "
            "a beginner answer needs no advanced nuance. Do not penalize a spoken conceptual answer for "
            "lacking code or syntax. Use exactly one verdict: "
            '"correct" when the final meaning communicates the core concept accurately and sufficiently; '
            "minor wording issues, harmless terminology imprecision, disfluencies, and omitted optional "
            'detail must remain "correct". '
            '"partial" only when meaningful understanding is present but a genuine conceptual omission, '
            "unresolved ambiguity, or limited inaccuracy affects the answer; never use it for wording or "
            "fluency alone. "
            '"wrong" only for a genuine conceptual misunderstanding, materially incorrect or contradictory '
            "final answer, irrelevant response, or no answer; never use it merely for casual vocabulary or "
            "an imperfect analogy whose intended concept is clear. Friendliness must not turn a genuinely "
            "incorrect or confused answer into a correct one. If the answer is empty or a timeout with no "
            'content, classify it as "wrong".\n\n'
            "For the reason field: write one encouraging, constructive, specific sentence of at most "
            "25 words. Acknowledge what the candidate understood whenever anything is valid, then explain "
            "any conceptual gap without scolding. If the concept is correct but terminology is informal, "
            f"{terminology_refinement}Avoid blunt "
            "wording such as 'Wrong because...' and never criticize speech style.\n\n"
            f"For the ideal_answer field: {ideal_answer_guidance} Always provide it regardless of verdict.\n\n"
            f"{beginner_final_rule}"
            "Respond ONLY with valid JSON in this exact shape:\n"
            "{\n"
            '  "verdict": "correct" | "partial" | "wrong",\n'
            '  "reason": "<encouraging, specific sentence, max 25 words>",\n'
            '  "ideal_answer": "<natural, difficulty-matched interview answer>"\n'
            "}"
        )

    user_prompt = (
        f"Question: {question}\n"
        f"Candidate answer: {answer or '(no answer given)'}"
    )
    raw = chat_fn(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )
    result = _json_object(raw)
    if result.get("verdict") not in {"correct", "partial", "wrong"}:
        raise ValueError("The AI returned an invalid answer verdict.")

    result["reason"] = _clip_sentence(result.get("reason", ""), max_words=25)
    result["ideal_answer"] = _clip_sentence(
        result.get("ideal_answer", ""),
        max_words=IDEAL_ANSWER_MAX_WORDS.get(difficulty, 90),
    )
    return {key: result[key] for key in ("verdict", "reason", "ideal_answer")}


def generate_ideal_answer(question, difficulty, round_type="technical", *, chat_fn):
    """Generate only a model answer for a deterministic timeout verdict."""
    system_prompt = (
        f"{_ideal_answer_guidance(difficulty, round_type)} "
        "Respond with plain text only, no JSON and no preamble."
    )
    result = chat_fn(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
    ).strip()
    return _clip_sentence(
        result,
        max_words=IDEAL_ANSWER_MAX_WORDS.get(difficulty, 90),
    )


def evaluate_interview(round_type, subject, difficulty, qa_pairs, *, chat_fn):
    """
    qa_pairs: list of dicts [{"question": ..., "answer": ..., "time_taken_sec": ...}, ...]
    Returns a dict with scores, strengths, weaknesses, feedback -- ready to store in MySQL.
    """
    if round_type == "hr":
        system_prompt = (
            "You are an expert HR and behavioral interview evaluator. Score the full spoken Q&A transcript "
            "at the stated difficulty. Judge the final "
            f"{HR_LEVEL_SCORING.get(difficulty, '')}"
            "intended meaning and substance of each answer. Ignore fillers, hesitation, repetition, "
            "self-corrections, casual phrasing, and imperfect structure. Do not reward corporate "
            "buzzwords or penalize candidates for lacking them. Evaluate response relevance and "
            "completeness, communication clarity, behavioral judgment, ownership, self-awareness, "
            "and confidence appropriate to the question and difficulty. Examples from education, "
            "projects, volunteering, clubs, and everyday responsibilities are valid. Do not require "
            "formal work experience or perfect STAR formatting. For database compatibility, the "
            "technical_accuracy field represents HR answer relevance, completeness, and behavioral "
            "judgment in this round; it does not represent technical knowledge. For any entry where "
            "timed_out is true or answer is empty/None, treat that question as 0/10 for this field "
            "and factor it into overall_score. Do not give credit for unanswered questions. Keep all "
            "feedback encouraging, specific, and actionable. Respond ONLY with valid JSON in exactly "
            "this shape. Return strengths and weaknesses as 2 to 4 distinct, concise points each. "
            "Each point must be one short sentence or phrase, with no bullet character or numbering "
            "inside the string. "
            "Use this shape:\n"
            "{\n"
            '  "overall_score": <0-10 number>,\n'
            '  "technical_accuracy": <0-10 number>,\n'
            '  "communication_clarity": <0-10 number>,\n'
            '  "confidence": <0-10 number>,\n'
            '  "strengths": ["<concise strength>", "<concise strength>"],\n'
            '  "weaknesses": ["<concise area to improve>", "<concise area to improve>"],\n'
            '  "feedback": "<short actionable paragraph>"\n'
            "}"
        )
    else:
        system_prompt = (
            "You are an interview evaluator. Score the full Q&A transcript. This is a spoken "
            "Conversation Mode interview: "
            f"{BEGINNER_TECHNICAL_RUBRIC if difficulty == 'beginner' else ''}"
            f"{TECHNICAL_LEVEL_SCORING.get(difficulty, '')}"
            "technical questions are expected to be answered through concepts, explanations, "
            "comparisons, logical reasoning, problem-solving approach, debugging approach, "
            "real-world scenarios, and communication clarity, not by writing or dictating code. "
            "Evaluate technical understanding, communication skills, logical reasoning, "
            "problem-solving approach, and confidence. Do not penalize the candidate for not "
            "providing code snippets, function implementations, algorithm implementations, or "
            "exact syntax. For any entry where timed_out is true or answer is empty/None, treat "
            "that question as scoring 0/10 for technical_accuracy on that question and factor it "
            "into the overall_score accordingly. Do not give credit for unanswered questions. "
            "Mention unanswered or timed-out questions in the weaknesses field if there were any. "
            "Return strengths and weaknesses as 2 to 4 distinct, concise points each. Each point "
            "must be one short sentence or phrase, with no bullet character or numbering inside "
            "the string. Respond ONLY with valid JSON in exactly this shape:\n"
            "{\n"
            '  "overall_score": <0-10 number>,\n'
            '  "technical_accuracy": <0-10 number>,\n'
            '  "communication_clarity": <0-10 number>,\n'
            '  "confidence": <0-10 number>,\n'
            '  "strengths": ["<concise strength>", "<concise strength>"],\n'
            '  "weaknesses": ["<concise area to improve>", "<concise area to improve>"],\n'
            '  "feedback": "<short actionable paragraph>"\n'
            "}"
        )

    transcript = json.dumps(qa_pairs, indent=2)
    user_prompt = (
        f"Round: {round_type}, Subject: {subject}, Difficulty: {difficulty}\n\n"
        f"Transcript:\n{transcript}"
    )

    raw = chat_fn(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )

    result = _json_object(raw)
    for field in (
        "overall_score",
        "technical_accuracy",
        "communication_clarity",
        "confidence",
    ):
        result[field] = _score(result.get(field), field)
    for field in ("strengths", "weaknesses"):
        points = result.get(field)
        if not isinstance(points, list):
            raise ValueError(f"The AI returned invalid {field} feedback.")
        cleaned_points = [
            point.strip().lstrip("-* \t").strip()
            for point in points
            if isinstance(point, str) and point.strip()
        ]
        if not 2 <= len(cleaned_points) <= 4:
            raise ValueError(f"The AI must return 2 to 4 {field} points.")
        # The existing MySQL columns are TEXT, so store the arrays as JSON
        # without requiring a schema migration.
        result[field] = json.dumps(cleaned_points, ensure_ascii=False)

    if not isinstance(result.get("feedback"), str) or not result["feedback"].strip():
        raise ValueError("The AI returned invalid feedback.")
    result["feedback"] = result["feedback"].strip()
    return result


def evaluate_answers_batch(round_type, subject, difficulty, qa_pairs, *, chat_fn):
    """Evaluate all submitted answers in one request, preserving input order."""
    prompt = (
        f"Evaluate all Q&A pairs for a {round_type} interview at {difficulty} difficulty. "
        f"{BEGINNER_TECHNICAL_RUBRIC if round_type == 'technical' and difficulty == 'beginner' else ''}"
        f"{(TECHNICAL_LEVEL_SCORING if round_type == 'technical' else HR_LEVEL_SCORING).get(difficulty, '')}"
        "Return one result per pair in the same order. Use verdict correct, partial, or wrong; "
        "include question_id, a concise reason, and recommended ideal_answer. Return ONLY JSON in this shape: "
        '{"evaluations":[{"question_id":1,"verdict":"correct|partial|wrong","reason":"...","ideal_answer":"..."}]}\n'
        f"Pairs: {json.dumps(qa_pairs, ensure_ascii=False)}"
    )
    value = _json_object(chat_fn([{"role": "system", "content": prompt}], json_mode=True))
    evaluations = value.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != len(qa_pairs):
        raise ValueError("The AI returned an invalid batch evaluation.")
    for item in evaluations:
        if item.get("question_id") is None or item.get("verdict") not in {"correct", "partial", "wrong"}:
            raise ValueError("The AI returned an invalid batch verdict.")
    return evaluations



