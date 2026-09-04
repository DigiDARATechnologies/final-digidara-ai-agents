import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from cert_app.config import get_settings
from cert_app.db import chat_repository
from cert_app.agents.question_agent import generate_questions
from cert_app.agents.evaluation_agent import evaluate_answer
from cert_app.services.usage_service import record_llm_usage

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChatTurnResult:
    messages: List[Dict]
    session_status: str
    current_question_index: int
    total_questions: int
    score_percentage: Optional[float] = None
    passed: Optional[bool] = None


def _sanitize_message_for_client(msg: Dict) -> Dict:
    """Strips server-only secret fields (correct_answer, expected_answer, etc.) from message metadata."""
    clean_msg = {
        "id": msg.get("id"),
        "session_id": msg.get("session_id"),
        "role": msg.get("role"),
        "content": msg.get("content"),
        "message_type": msg.get("message_type"),
        "created_at": msg.get("created_at")
    }
    raw_meta = msg.get("metadata")
    if isinstance(raw_meta, dict):
        clean_meta = {}
        for k, v in raw_meta.items():
            if k not in ("correct_answer", "expected_answer", "questions_bank", "server_secret"):
                clean_meta[k] = v
        clean_msg["metadata"] = clean_meta
    else:
        clean_msg["metadata"] = None
    return clean_msg


def _find_current_question_meta(history: List[Dict], question_index: int) -> Optional[Dict]:
    """Finds the stored metadata for a given question index from message history."""
    for msg in reversed(history):
        meta = msg.get("metadata")
        if isinstance(meta, dict) and meta.get("question_index") == question_index:
            return meta
    return None


def _clean_topic_name(raw_topic: str) -> str:
    return raw_topic.strip()


def analyze_user_message(session_id: str, user_message: str) -> dict:
    """Use the LLM to classify if the user wants to start an exam or just chat, taking history into account."""
    try:
        # Load last 6 messages of history for context
        history = chat_repository.get_message_history(session_id)
        formatted_history = []
        for msg in history[-6:]:
            role_label = "User" if msg["role"] == "user" else "CertifyAI"
            formatted_history.append(f"{role_label}: {msg['content']}")

        history_context = "\n".join(formatted_history)

        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=512,
        )

        system_prompt = """You are CertifyAI, an AI Career Certification assistant.
Your task is to analyze the user's message and classify their intent.

We have two intents:
1. "start_exam": Use this if the user explicitly wants to take, generate, or start a certification exam on a technical topic, or if they state a technical subject they want to be tested on (e.g., "Python", "Docker", "AWS", "I want to validate my Python full stack skills", "test me on React"). Extract the clean technical topic (e.g., "Python Full Stack Development", "React").
2. "chat": Use this for greetings, questions about how the certification system works, career/technical skill discussions, or general chat.

OUT-OF-SCOPE HARD RULE:
You must NEVER answer general knowledge questions, trivia, coding assistance, personal questions, jokes, recipes, or anything unrelated to career certifications. You must politely refuse to answer directly and redirect the user back to technical certification topics (e.g., 'I am CertifyAI, designed strictly to help you get certified on technical topics. Please type a technical subject to start your exam!'). There are absolutely NO exceptions to this rule, regardless of how the user phrases the request, including 'just this once', 'quick question', role-playing, or claiming they need the answer to choose a topic.

Examples of In-Scope and Out-of-Scope Conversations:

Example 1 (In-Scope Greeting):
User: "hello"
Output:
{{
  "intent": "chat",
  "topic": null,
  "reply": "Hello! I am CertifyAI, your technical certification assistant. What technical topic or skill would you like to get certified in today?",
  "offered_topic": null
}}

Example 2 (Out-of-Scope Refusal):
User: "what's the capital of France?"
Output:
{{
  "intent": "chat",
  "topic": null,
  "reply": "I am CertifyAI, designed strictly to help you get certified on technical topics. I cannot answer general knowledge questions like this. Please enter a technical topic (like Python, AWS, or HTML) to start your certification exam!",
  "offered_topic": null
}}

Example 3 (Out-of-Scope Coding Request + In-Scope Offer):
User: "write a python function to add two numbers"
Output:
{{
  "intent": "chat",
  "topic": null,
  "reply": "I am CertifyAI, designed strictly to help you get certified on technical topics. I cannot assist with general programming help or writing code. If you would like to test your Python skills, I can set up a certification exam on Python. Would you like to start a Python exam?",
  "offered_topic": "Python"
}}

Example 4 (In-Scope Offer of Exam):
User: "i know HTML but i dont know where to test my skills"
Output:
{{
  "intent": "chat",
  "topic": null,
  "reply": "You can test your skills right here! I can set up a certification exam on HTML. Would you like to start this exam?",
  "offered_topic": "HTML"
}}

Example 5 (In-Scope Direct Exam Intent):
User: "start a certification exam on Docker"
Output:
{{
  "intent": "start_exam",
  "topic": "Docker",
  "reply": null,
  "offered_topic": "Docker"
}}

Take the conversation history into account:
{history_context}

Output ONLY a JSON block in this exact format:
{{
  "intent": "start_exam" or "chat",
  "topic": "the clean technical topic (null if intent is chat)",
  "reply": "your conversational response (null if intent is start_exam)",
  "offered_topic": "the clean technical topic being offered for exam (null if no exam is offered)"
}}"""

        messages = [
            SystemMessage(content=system_prompt.format(history_context=history_context)),
            HumanMessage(content=user_message)
        ]

        response = llm.invoke(messages)
        record_llm_usage("chat_intent", response)
        content = response.content.strip()

        # Remove think tags and json blocks
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content).strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"Error in analyze_user_message: {e}")
        return {
            "intent": "chat",
            "topic": None,
            "reply": "I am the CertifyAI evaluator, designed strictly to help you get certified on technical topics. Please enter a technical topic (like Python, AWS, or Docker) to start your certification!",
            "offered_topic": None
        }


def analyze_confirmation(session_id: str, user_message: str) -> bool:
    """Uses the LLM to classify if the user's message is an affirmation (yes) or negation (no) based on context."""
    try:
        history = chat_repository.get_message_history(session_id)
        formatted_history = []
        for msg in history[-6:]:
            role_label = "User" if msg["role"] == "user" else "CertifyAI"
            formatted_history.append(f"{role_label}: {msg['content']}")
        history_context = "\n".join(formatted_history)

        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=50,
        )
        system_prompt = (
            "You are a binary classifier. Analyze the conversation history and the user's latest response "
            "to determine if they are confirming/agreeing to start the certification exam offered.\n\n"
            "History:\n"
            "{history_context}\n\n"
            "Determine if the user's latest message below is an affirmation (e.g., 'yes', 'sure', 'ok', 'let's do it', 'yes, start the exam') "
            "or a negation (e.g., 'no', 'not now', 'keep chatting', 'no, let's keep chatting'). "
            "Output ONLY 'YES' or 'NO'."
        )
        messages = [
            SystemMessage(content=system_prompt.format(history_context=history_context)),
            HumanMessage(content=user_message)
        ]
        response = llm.invoke(messages)
        record_llm_usage("chat_confirmation", response)
        ans = response.content.strip().upper()
        return "YES" in ans
    except Exception as e:
        logger.error(f"Error in analyze_confirmation: {e}")
        return False


def bg_generate_questions(session_id: str, topic: str, choice: str):
    """Generate 30 exam questions in the background and transition session state."""
    try:
        logger.info(f"[Chat] [BG] Generating 30 questions ({choice}) for topic: {topic}")
        questions = generate_questions(topic, num_questions=30, difficulty=choice)
        total = len(questions)

        # Persist questions in the session
        chat_repository.store_session_questions(session_id, questions)
        chat_repository.update_session_status(
            session_id=session_id,
            status="in_exam",
            current_question_index=0,
            score=None
        )

        next_idx = 0
        next_q = questions[next_idx]
        msg_type = "mcq_question" if next_q.get("options") else "freetext_question"
        next_meta = {
            "question_index": next_idx,
            "phase": "exam",
            "options": next_q.get("options", []),
            "correct_answer": next_q.get("correct_answer", ""),
            "expected_answer": next_q.get("expected_answer", ""),
            "questions_bank": questions
        }

        chat_repository.append_message(
            session_id,
            "assistant",
            f"Question {next_idx + 1} of {total}:\n{next_q['question']}",
            msg_type,
            next_meta
        )
        logger.info(f"[Chat] [BG] Successfully generated questions and saved Question 1 for session: {session_id}")
    except Exception as e:
        logger.error(f"[Chat] [BG] Error generating questions for session {session_id}: {e}")
        chat_repository.update_session_status(
            session_id=session_id,
            status="generation_failed"
        )
        chat_repository.append_message(
            session_id,
            "assistant",
            "Something went wrong generating your exam, please try again.",
            "text"
        )


def default_bg_runner(fn: Callable, *args, **kwargs) -> None:
    """Default background task runner: spawns a daemon thread."""
    thread = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    thread.start()


def handle_message(session_id: str, user_message: str, bg_runner: Callable = default_bg_runner) -> ChatTurnResult:
    """
    Main entry point for driving the conversational exam state machine.

    States:
      onboarding  → user provides a topic → generate 40 questions → ready
      ready       → session has questions stored, waiting for user to click Take Exam
                    (any message here just reminds user to click the button)
      in_exam     → chat-mode exam flow (answer Q1..Qn in chat)
      grading     → compute final score, issue certificate if passed
      completed/failed → session closed
    """
    session = chat_repository.get_session(session_id)
    if not session:
        raise ValueError(f"Chat session '{session_id}' not found.")

    status = session.get("status", "onboarding")
    user_message_clean = user_message.strip()

    if status == "generating":
        prompt_msg = chat_repository.append_message(
            session_id,
            "assistant",
            "Please wait, your exam is still being generated.",
            "text"
        )
        return ChatTurnResult(
            messages=[_sanitize_message_for_client(prompt_msg)],
            session_status="generating",
            current_question_index=0,
            total_questions=0
        )

    if status == "generation_failed":
        chat_repository.update_session_status(session_id, "onboarding")
        status = "onboarding"

    # ── Closed Session Handler ──────────────────────────────────────────────────
    if status in ("completed", "failed"):
        close_msg = chat_repository.append_message(
            session_id,
            "assistant",
            "This exam session is closed. Please start a new exam session to try another topic.",
            "text"
        )
        return ChatTurnResult(
            messages=[_sanitize_message_for_client(close_msg)],
            session_status=status,
            current_question_index=session.get("current_question_index", 0),
            total_questions=session.get("total_questions", 0),
            score_percentage=session.get("score"),
            passed=(status == "completed")
        )

    # ── ONBOARDING State Handler (select topic, ask difficulty) ─────────────────
    # ── ONBOARDING State Handler (select topic, ask difficulty) ─────────────────
    if status == "onboarding":
        # 1. Check if the user is replying to a confirmation request
        history = chat_repository.get_message_history(session_id)
        last_msg = history[-1] if history else None
        is_waiting_for_confirmation = False
        temp_topic = None

        if last_msg and last_msg["role"] == "assistant" and last_msg["message_type"] == "mcq_question":
            meta = last_msg.get("metadata") or {}
            if meta.get("phase") == "confirm_exam":
                is_waiting_for_confirmation = True
                temp_topic = meta.get("temp_topic")

        if is_waiting_for_confirmation:
            # Analyze confirmation choice
            is_confirmed = analyze_confirmation(session_id, user_message_clean)
            if is_confirmed:
                # User said YES!
                chat_repository.append_message(session_id, "user", user_message_clean, "text")
                # Transition status to calibrating and save topic
                chat_repository.update_session_status(
                    session_id=session_id,
                    status="calibrating",
                    topic=temp_topic
                )
                prompt_msg = chat_repository.append_message(
                    session_id,
                    "assistant",
                    f"Great! Let's set up your **{temp_topic}** certification exam.\n\n"
                    f"What **difficulty level** would you like to target?",
                    "mcq_question",
                    {"options": ["Beginner", "Intermediate", "Advanced", "Mixed"]}
                )
                return ChatTurnResult(
                    messages=[_sanitize_message_for_client(prompt_msg)],
                    session_status="calibrating",
                    current_question_index=0,
                    total_questions=0
                )
            else:
                # User said NO! Keep chatting.
                chat_repository.append_message(session_id, "user", user_message_clean, "text")
                reply_text = "No problem! What else would you like to chat about?"
                prompt_msg = chat_repository.append_message(session_id, "assistant", reply_text, "text")
                return ChatTurnResult(
                    messages=[_sanitize_message_for_client(prompt_msg)],
                    session_status="onboarding",
                    current_question_index=0,
                    total_questions=0
                )

        # 2. Otherwise, handle standard conversation/intent classification using LLM
        analysis = analyze_user_message(session_id, user_message_clean)
        intent = analysis.get("intent", "chat")
        topic = analysis.get("topic")
        offered_topic = analysis.get("offered_topic") or (topic if intent == "start_exam" else None)

        chat_repository.append_message(session_id, "user", user_message_clean, "text")

        if offered_topic:
            # We have an exam offer!
            temp_topic = _clean_topic_name(offered_topic)
            reply_text = analysis.get("reply") or f"I can set up a certification exam on **{temp_topic}**. Would you like to start this exam?"
            prompt_msg = chat_repository.append_message(
                session_id,
                "assistant",
                reply_text,
                "mcq_question",
                {
                    "phase": "confirm_exam",
                    "options": ["Yes, start the exam", "No, let's keep chatting"],
                    "temp_topic": temp_topic
                }
            )
            return ChatTurnResult(
                messages=[_sanitize_message_for_client(prompt_msg)],
                session_status="onboarding",
                current_question_index=0,
                total_questions=0
            )

        # Otherwise, handle standard conversational reply (no exam offered)
        reply_text = analysis.get("reply") or "I am the CertifyAI evaluator, designed strictly to help you get certified on technical topics. Please type a technical subject (like Python, AWS, or Docker) to start your certification!"
        prompt_msg = chat_repository.append_message(session_id, "assistant", reply_text, "text")
        return ChatTurnResult(
            messages=[_sanitize_message_for_client(prompt_msg)],
            session_status="onboarding",
            current_question_index=0,
            total_questions=0
        )

    # ── CALIBRATING State Handler (user selected difficulty, generate questions) ──
    if status == "calibrating":
        # Capture selected difficulty
        choice = user_message_clean.strip().lower()
        if choice not in ("beginner", "intermediate", "advanced", "mixed"):
            # User interrupted the difficulty calibration flow or asked an unrelated question
            analysis = analyze_user_message(session_id, user_message_clean)
            reply_text = analysis.get("reply") or "I am the CertifyAI evaluator, designed strictly to help you get certified on technical topics."
            reply_text += "\n\nPlease choose a difficulty level (Beginner, Intermediate, Advanced, Mixed) to begin your exam."
            
            chat_repository.append_message(session_id, "user", user_message_clean, "text")
            prompt_msg = chat_repository.append_message(
                session_id,
                "assistant",
                reply_text,
                "mcq_question",
                {"options": ["Beginner", "Intermediate", "Advanced", "Mixed"]}
            )
            return ChatTurnResult(
                messages=[_sanitize_message_for_client(prompt_msg)],
                session_status="calibrating",
                current_question_index=0,
                total_questions=0
            )

        chat_repository.append_message(session_id, "user", user_message_clean, "text")
        topic = session.get("topic", "Exam")

        # Acknowledge immediately
        ack_msg = chat_repository.append_message(
            session_id,
            "assistant",
            f"⚡ Generating your 30-question **{choice.capitalize()}** certification exam for **'{topic}'**...\n"
            "This usually takes 15–20 seconds. Please wait!",
            "text"
        )

        chat_repository.update_session_status(
            session_id=session_id,
            status="generating"
        )

        # Delegate background execution to the injected runner.
        # Production uses default_bg_runner (real thread); tests inject a sync runner.
        bg_runner(bg_generate_questions, session_id, topic, choice)

        # If the runner completed synchronously (e.g. a test sync_runner), the session
        # status is already final. Re-read and return the correct state immediately.
        refreshed = chat_repository.get_session(session_id)
        refreshed_status = refreshed.get("status") if refreshed else "generating"

        if refreshed_status == "in_exam":
            history = chat_repository.get_message_history(session_id)
            q_msg = history[-1]
            return ChatTurnResult(
                messages=[
                    _sanitize_message_for_client(ack_msg),
                    _sanitize_message_for_client(q_msg)
                ],
                session_status="in_exam",
                current_question_index=0,
                total_questions=len(refreshed.get("questions") or [])
            )

        if refreshed_status == "generation_failed":
            history = chat_repository.get_message_history(session_id)
            err_msg = history[-1]
            return ChatTurnResult(
                messages=[
                    _sanitize_message_for_client(ack_msg),
                    _sanitize_message_for_client(err_msg)
                ],
                session_status="generation_failed",
                current_question_index=0,
                total_questions=0
            )

        # Runner was asynchronous — generation is still in progress.
        return ChatTurnResult(
            messages=[_sanitize_message_for_client(ack_msg)],
            session_status="generating",
            current_question_index=0,
            total_questions=0
        )

    # ── READY State Handler (exam generated, waiting for user to click Take Exam) ──
    if status == "ready":
        # User sent a message while in ready state — remind them
        chat_repository.append_message(session_id, "user", user_message_clean, "text")

        topic = session.get("topic", "your topic")
        remind_meta = {
            "topic": topic,
            "total_questions": session.get("total_questions", 30),
            "session_id": session_id,
            "exam_url": f"/exam?session_id={session_id}&topic={topic}"
        }
        remind_msg = chat_repository.append_message(
            session_id,
            "assistant",
            f"Your **30-question exam for '{topic}'** is ready and waiting!\n\n"
            "Click the **Take Exam ⚡** button above to launch it.",
            "take_exam_card",
            remind_meta
        )
        return ChatTurnResult(
            messages=[_sanitize_message_for_client(remind_msg)],
            session_status="ready",
            current_question_index=0,
            total_questions=session.get("total_questions", 30)
        )

    # ── IN_EXAM State Handler (chat-mode fallback) ───────────────────────────────
    if status == "in_exam":
        if user_message_clean == "force_fail_due_to_tab_switches":
            # This is deliberately terminal: the browser may be refreshed or
            # closed after the third visibility violation, so the failure must
            # be recorded server-side rather than only shown in the UI.
            # `chat_messages.message_type` has no `system` enum value. Keep
            # this audit marker as ordinary text so the terminal failure can
            # always be committed.
            chat_repository.append_message(session_id, "user", user_message_clean, "text")
            chat_repository.update_session_status(session_id, status="failed", score=0.0)
            failure_msg = chat_repository.append_message(
                session_id,
                "assistant",
                "🚫 Exam closed: three tab switches were detected. This certification attempt has been marked as failed.",
                "certificate_card",
                {"passed": False, "score_percentage": 0.0, "reason": "tab_switch_limit"},
            )
            return ChatTurnResult(
                messages=[_sanitize_message_for_client(failure_msg)],
                session_status="failed",
                current_question_index=session.get("current_question_index", 0),
                total_questions=session.get("total_questions", 0),
                score_percentage=0.0,
                passed=False,
            )

        if user_message_clean == "force_submit_exam_due_to_tab_switches":
            chat_repository.update_session_status(
                session_id=session_id,
                status="grading",
                current_question_index=session.get("current_question_index", 0)
            )
            return handle_message(session_id, user_message)

        history = chat_repository.get_message_history(session_id)
        current_idx = session.get("current_question_index", 0)

        # Append user answer
        chat_repository.append_message(session_id, "user", user_message_clean, "text")


        q_meta = _find_current_question_meta(history, current_idx)
        if not q_meta:
            for m in reversed(history):
                if isinstance(m.get("metadata"), dict) and "questions_bank" in m["metadata"]:
                    q_meta = m["metadata"]
                    break

        questions_bank = (q_meta or {}).get("questions_bank", [])
        current_q = questions_bank[current_idx] if current_idx < len(questions_bank) else {}

        # Grade answer
        opts = current_q.get("options", [])
        if opts:
            is_correct = (user_message_clean.strip() == str(current_q.get("correct_answer", "")).strip())
            score = 1 if is_correct else 0
            feedback = (
                f"✅ Correct! {current_q.get('expected_answer', '')}"
                if is_correct else
                f"❌ Incorrect. The correct answer was: **{current_q.get('correct_answer', '')}**"
            )
        else:
            eval_res = evaluate_answer(
                current_q.get("question", ""),
                current_q.get("expected_answer", ""),
                user_message_clean
            )
            score = eval_res["score"]
            feedback = eval_res["feedback"]

        fb_msg = chat_repository.append_message(
            session_id, "assistant", feedback, "feedback", {"score_delta": score, "phase": "exam"}
        )

        next_idx = current_idx + 1
        total_questions = session.get("total_questions", len(questions_bank))

        if next_idx < total_questions and next_idx < len(questions_bank):
            chat_repository.update_session_status(session_id, "in_exam", current_question_index=next_idx)
            next_q = questions_bank[next_idx]
            msg_type = "mcq_question" if next_q.get("options") else "freetext_question"
            next_meta = {
                "question_index": next_idx,
                "phase": "exam",
                "options": next_q.get("options", []),
                "correct_answer": next_q.get("correct_answer", ""),
                "expected_answer": next_q.get("expected_answer", ""),
                "questions_bank": questions_bank
            }
            q_msg = chat_repository.append_message(
                session_id,
                "assistant",
                f"Question {next_idx + 1} of {total_questions}:\n{next_q['question']}",
                msg_type,
                next_meta
            )
            return ChatTurnResult(
                messages=[_sanitize_message_for_client(fb_msg), _sanitize_message_for_client(q_msg)],
                session_status="in_exam",
                current_question_index=next_idx,
                total_questions=total_questions
            )

        # All exam questions answered → grading
        chat_repository.update_session_status(session_id, "grading", current_question_index=next_idx)
        status = "grading"

    # ── GRADING State Handler ────────────────────────────────────────────────────
    if status == "grading":
        history = chat_repository.get_message_history(session_id)

        correct_count = 0
        total_graded = 0
        for msg in history:
            meta = msg.get("metadata")
            if isinstance(meta, dict) and "score_delta" in meta and meta.get("phase") == "exam":
                correct_count += int(meta["score_delta"])
                total_graded += 1

        total = max(session.get("total_questions", 1), total_graded, 1)
        score_pct = round((correct_count / total) * 100, 2)
        passed = score_pct >= settings.PASS_SCORE
        final_status = "completed" if passed else "failed"

        chat_repository.update_session_status(
            session_id=session_id,
            status=final_status,
            score=score_pct
        )

        cert_id = None
        cert_number = None
        if passed:
            try:
                from cert_app.services.exam_service import issue_certificate_for_chat_session
                cert_res = issue_certificate_for_chat_session(session["user_id"], session.get("topic", ""), score_pct)
                cert_id = cert_res.get("certificate_id")
                cert_number = cert_res.get("certificate_number")
                if cert_id:
                    chat_repository.attach_certificate(session_id, cert_id)
            except Exception as e:
                logger.error(f"Failed to issue certificate for chat session '{session_id}': {e}")

        # A pass means the exam result passed—not necessarily that the PDF
        # was persisted.  Keep those states distinct so every client can
        # offer a download only after a certificate record actually exists.
        cert_card_meta = {
            "topic": session.get("topic", ""),
            "score_percentage": score_pct,
            "passed": passed,
            "certificate_ready": bool(cert_id),
            "certificate_id": cert_id,
            "certificate_number": cert_number
        }

        card_content = (
            f"🎉 Congratulations! You **PASSED** the '{session.get('topic')}' certification with **{score_pct}%**!"
            if passed and cert_id else
            f"🎉 You passed the '{session.get('topic')}' certification with **{score_pct}%**, but the certificate file could not be issued. Please contact support or retry after the service is restored."
            if passed else
            f"Exam Complete. Your score was **{score_pct}%**. Passing threshold is {settings.PASS_SCORE}%. Better luck next time!"
        )

        card_msg = chat_repository.append_message(
            session_id,
            "assistant",
            card_content,
            "certificate_card",
            cert_card_meta
        )

        return ChatTurnResult(
            messages=[_sanitize_message_for_client(card_msg)],
            session_status=final_status,
            current_question_index=session.get("total_questions", 0),
            total_questions=session.get("total_questions", 0),
            score_percentage=score_pct,
            passed=passed
        )

    raise ValueError(f"Unhandled session status '{status}'")
