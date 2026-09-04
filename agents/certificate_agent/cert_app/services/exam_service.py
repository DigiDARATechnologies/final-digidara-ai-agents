import uuid
import logging
import os
import smtplib
import ssl
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List, Dict, Optional

from cert_app.db.database import get_connection
from cert_app.agents.question_agent import generate_questions
from cert_app.agents.evaluation_agent import evaluate_answer
import json
from cert_app.services.certificate_generator import generate_certificate
from cert_app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def is_topic_course(topic: str) -> bool:
    t = topic.strip().lower()
    course_list = {
        "python fundamentals",
        "artificial intelligence", "data science with python", "machine learning",
        "deep learning", "natural language processing", "computer vision",
        "big data analytics", "robotics & automation", "statistical modeling", "ai ethics",
        "web development", "cloud computing", "cybersecurity", "database systems",
        "software engineering", "mobile app development", "devops & ci/cd",
        "internet of things", "it project management", "network security",
        "data structures", "operating systems", "computer architecture",
        "compiler design", "theory of computation", "distributed systems",
        "parallel computing", "computer graphics", "java programming", "c++ advanced",
        "digital logic design", "microprocessors", "signal processing",
        "vlsi design", "embedded systems", "wireless communication",
        "antennas", "control systems", "optical fibers", "analog circuits",
        "electric circuits", "power systems", "electrical machines",
        "power electronics", "renewable energy", "smart grid",
        "high voltage engineering", "instrumentation", "control engineering", "circuit theory",
        "thermodynamics", "fluid mechanics", "strength of materials",
        "manufacturing technology", "machine design", "heat transfer",
        "cad/cam", "automobile engineering", "mechatronics", "ic engines",
        "structural engineering", "geotechnical engineering", "transportation engineering",
        "hydraulics", "surveying", "construction management",
        "environmental engineering", "concrete technology", "hydrology", "building materials"
    }
    if t in course_list:
        return True
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM cert_subjects WHERE LOWER(TRIM(name)) = %s", (t,))
        row = cursor.fetchone()
        cursor.close(); conn.close()
        return row is not None
    except Exception:
        return False


# ─── Attempt Tracking ─────────────────────────────────────────────────────────

def check_attempt_allowed(user_id: int, topic: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT attempts, is_locked FROM attempt_tracking WHERE user_id=%s AND topic=%s",
            (user_id, topic)
        )
        row = cursor.fetchone()
        if not row:
            return True
        return not row["is_locked"] and row["attempts"] < settings.MAX_ATTEMPTS
    finally:
        cursor.close()
        conn.close()


def increment_attempt(user_id: int, topic: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO attempt_tracking (user_id, topic, attempts)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE
                attempts = attempts + 1,
                is_locked = IF(attempts + 1 >= %s, TRUE, FALSE)
        """, (user_id, topic, settings.MAX_ATTEMPTS))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def get_attempt_info(user_id: int, topic: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT attempts, is_locked FROM attempt_tracking WHERE user_id=%s AND topic=%s",
            (user_id, topic)
        )
        row = cursor.fetchone()
        if not row:
            return {"attempts": 0, "is_locked": False, "remaining": settings.MAX_ATTEMPTS}
        remaining = max(0, settings.MAX_ATTEMPTS - row["attempts"])
        return {**row, "remaining": remaining}
    finally:
        cursor.close()
        conn.close()


# ─── Exam Operations ───────────────────────────────────────────────────────────

def _get_cached_questions(topic: str) -> Optional[List[Dict]]:
    """
    Look up pre-generated questions from cert_question_cache for a given topic.
    Returns the parsed list if found and ready, else None (fall back to live gen).
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT cqc.questions_json
               FROM cert_question_cache cqc
               JOIN cert_subjects cs ON cqc.subject_id = cs.id
               WHERE LOWER(cs.name) = LOWER(%s) AND cs.questions_status = 'ready'
               ORDER BY cqc.generated_at DESC LIMIT 1""",
            (topic,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['questions_json'])
        return None
    except Exception:
        return None
    finally:
        cursor.close()
        conn.close()


def start_exam(user_id: int, username: str, topic: str) -> Dict:
    if not check_attempt_allowed(user_id, topic):
        raise PermissionError(
            f"Exam locked: Maximum {settings.MAX_ATTEMPTS} attempts reached for '{topic}'"
        )

    # Try pre-cached questions first (instant); fall back to live AI generation
    questions = _get_cached_questions(topic)
    if questions is None:
        questions = generate_questions(topic)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "INSERT INTO exams (user_id, topic, total_questions, status) VALUES (%s,%s,%s,'in_progress')",
            (user_id, topic, len(questions))
        )
        exam_id = cursor.lastrowid

        question_records = []
        for i, q in enumerate(questions):
            options_json = json.dumps(q.get("options", []))
            cursor.execute(
                "INSERT INTO questions (exam_id, question_text, expected_answer, options, correct_answer, difficulty, order_num) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (exam_id, q["question"], q.get("expected_answer", ""), options_json, q.get("correct_answer", ""), q.get("difficulty", "beginner"), i + 1)
            )
            question_records.append({
                "id": cursor.lastrowid,
                "question_text": q["question"],
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", "beginner"),
                "order_num": i + 1
            })

        conn.commit()
        increment_attempt(user_id, topic)
        attempt_info = get_attempt_info(user_id, topic)

        return {
            "exam_id": exam_id,
            "topic": topic,
            "total_questions": len(questions),
            "questions": question_records,
            "attempts_used": attempt_info["attempts"],
            "attempts_remaining": attempt_info["remaining"]
        }
    finally:
        cursor.close()
        conn.close()


def submit_exam(user_id: int, username: str, exam_id: int, answers: List[Dict]) -> Dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM exams WHERE id=%s AND user_id=%s", (exam_id, user_id))
        exam = cursor.fetchone()
        if not exam:
            raise ValueError("Exam not found or access denied")
        if exam["status"] not in ("started", "in_progress"):
            raise ValueError("Exam already completed")

        cursor.execute(
            "SELECT * FROM questions WHERE exam_id=%s ORDER BY order_num", (exam_id,)
        )
        questions = cursor.fetchall()

        answer_map = {a["question_id"]: a["answer"] for a in answers}
        correct_count = 0

        for q in questions:
            user_ans = answer_map.get(q["id"], "").strip()

            # Determine whether question is MCQ or free-text
            opts = []
            if q.get("options"):
                try:
                    opts = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
                except Exception:
                    opts = []

            if opts and len(opts) > 0:
                # MCQ exact match path
                is_correct = (user_ans == q["correct_answer"].strip())
                score = 1 if is_correct else 0
                feedback = f"Correct! {q['expected_answer']}" if is_correct else f"Incorrect. The correct answer was: {q['correct_answer']}. {q['expected_answer']}"
            else:
                # Free-text AI evaluation path
                eval_res = evaluate_answer(q["question_text"], q.get("expected_answer", ""), user_ans)
                score = eval_res["score"]
                feedback = eval_res["feedback"]

            cursor.execute(
                "INSERT INTO user_answers (exam_id, question_id, user_answer, score, ai_feedback) VALUES (%s,%s,%s,%s,%s)",
                (exam_id, q["id"], user_ans, score, feedback)
            )
            correct_count += score

        total = len(questions) or 1
        score_pct = round((correct_count / total) * 100, 2)
        passed = score_pct >= settings.PASS_SCORE
        status = "passed" if passed else "failed"

        cursor.execute(
            "UPDATE exams SET correct_answers=%s, score_percentage=%s, status=%s, completed_at=NOW() WHERE id=%s",
            (correct_count, score_pct, status, exam_id)
        )
        conn.commit()

        cert_id = None
        cert_number = None
        if passed:
            # ── Atomic sequential cert ID — safe for concurrent server requests ──
            # SELECT FOR UPDATE locks the last row so no two requests get the
            # same sequence number (race-condition-free on MySQL/MariaDB).
            year = datetime.now().year
            prefix = f"DDT-AI-{year}-"
            cursor.execute(
                "SELECT certificate_number FROM certificates "
                "WHERE certificate_number LIKE %s "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (f"{prefix}%",)
            )
            last = cursor.fetchone()
            if last:
                try:
                    seq = int(last["certificate_number"].rsplit("-", 1)[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            else:
                seq = 1
            cert_number = f"{prefix}{seq:03d}"
            is_course = is_topic_course(exam["topic"])
            file_path = generate_certificate(username, exam["topic"], score_pct, cert_number, is_course_final=is_course)
            cursor.execute(
                "INSERT INTO certificates (user_id, exam_id, topic, score_percentage, certificate_number, recipient_name, file_path) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (user_id, exam_id, exam["topic"], score_pct, cert_number, username, file_path)
            )
            conn.commit()
            cert_id = cursor.lastrowid

        # ── Link and Sync Conversational Session ──────────────────────────────
        cursor.execute("SELECT id FROM conversation_sessions WHERE exam_id = %s", (exam_id,))
        conv_session = cursor.fetchone()
        if conv_session:
            conv_sid = conv_session["id"]
            final_status = "completed" if passed else "failed"
            cursor.execute(
                "UPDATE conversation_sessions SET status = %s, score = %s, completed_at = NOW() WHERE id = %s",
                (final_status, score_pct, conv_sid)
            )
            
            # Append certificate card message to chat messages history
            cert_card_meta = {
                "topic": exam["topic"],
                "score_percentage": score_pct,
                "passed": passed,
                "certificate_ready": passed,
                "certificate_id": cert_id,
                "certificate_number": cert_number
            }
            card_content = (
                f"🎉 Congratulations! You **PASSED** the '{exam['topic']}' certification with **{score_pct}%**!"
                if passed else
                f"Exam Complete. Your score was **{score_pct}%**. Passing threshold is {settings.PASS_SCORE}%. Better luck next time!"
            )
            
            import uuid
            msg_id = str(uuid.uuid4())
            cursor.execute(
                """INSERT INTO chat_messages (id, session_id, role, content, message_type, metadata)
                   VALUES (%s, %s, 'assistant', %s, 'certificate_card', %s)""",
                (msg_id, conv_sid, card_content, json.dumps(cert_card_meta))
            )
            conn.commit()

        return {
            "exam_id": exam_id,
            "topic": exam["topic"],
            "total_questions": total,
            "correct_answers": correct_count,
            "score_percentage": score_pct,
            "status": status,
            "passed": passed,
            "certificate_id": cert_id,
            "certificate_number": cert_number
        }
    finally:
        cursor.close()
        conn.close()


def issue_certificate_for_chat_session(user_id: int, topic: str, score_pct: float) -> Dict:
    """Issue a verified certificate record and generate PDF file for a chat exam session."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
        user_row = cursor.fetchone()
        username = user_row["name"] if user_row else "Student"

        year = datetime.now().year
        prefix = f"DDT-AI-{year}-"
        cursor.execute(
            "SELECT certificate_number FROM certificates "
            "WHERE certificate_number LIKE %s "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (f"{prefix}%",)
        )
        last = cursor.fetchone()
        if last:
            try:
                seq = int(last["certificate_number"].rsplit("-", 1)[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        cert_number = f"{prefix}{seq:03d}"

        is_course = is_topic_course(topic)
        file_path = generate_certificate(username, topic, score_pct, cert_number, is_course_final=is_course)
        cursor.execute(
            "INSERT INTO certificates (user_id, exam_id, topic, score_percentage, certificate_number, recipient_name, file_path) VALUES (%s, NULL, %s, %s, %s, %s, %s)",
            (user_id, topic, score_pct, cert_number, username, file_path)
        )
        conn.commit()
        cert_id = cursor.lastrowid
        return {
            "certificate_id": cert_id,
            "certificate_number": cert_number,
            "file_path": file_path
        }
    finally:
        cursor.close()
        conn.close()


def ensure_certificate_for_completed_chat_session(session_id: str, user_id: int) -> Dict:
    """Return or issue the certificate for one already-passed chat attempt.

    This lets learners recover certificates from attempts completed before the
    shared React UI displayed the original certificate-card metadata.
    """
    from cert_app.db import chat_repository

    session = chat_repository.get_session(session_id)
    if not session or int(session["user_id"]) != int(user_id):
        raise ValueError("Exam session not found")
    if session.get("status") != "completed" or float(session.get("score") or 0) < settings.PASS_SCORE:
        raise ValueError("Only passed certification exams can receive a certificate")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        certificate_id = session.get("certificate_id")
        if certificate_id:
            cursor.execute(
                "SELECT id, certificate_number, file_path FROM certificates WHERE id = %s AND user_id = %s",
                (certificate_id, user_id),
            )
            existing = cursor.fetchone()
            if existing:
                return {
                    "certificate_id": existing["id"],
                    "certificate_number": existing["certificate_number"],
                    "file_path": existing.get("file_path"),
                }

        # Older passed sessions have no link. Reuse the matching issued
        # certificate when it exists, instead of creating a duplicate.
        cursor.execute(
            """SELECT id, certificate_number, file_path FROM certificates
               WHERE user_id = %s AND topic = %s
                 AND ABS(score_percentage - %s) < 0.01
                 AND issued_at >= %s
               ORDER BY issued_at ASC LIMIT 1""",
            (user_id, session.get("topic", ""), float(session.get("score") or 0), session.get("started_at")),
        )
        existing = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if existing:
        chat_repository.attach_certificate(session_id, existing["id"])
        return {
            "certificate_id": existing["id"],
            "certificate_number": existing["certificate_number"],
            "file_path": existing.get("file_path"),
        }

    issued = issue_certificate_for_chat_session(user_id, session.get("topic", ""), float(session.get("score") or 0))
    chat_repository.attach_certificate(session_id, issued["certificate_id"])
    return issued


def get_user_exams(user_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM exams WHERE user_id=%s ORDER BY started_at DESC", (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_exam_detail(user_id: int, exam_id: int) -> Dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM exams WHERE id=%s AND user_id=%s", (exam_id, user_id))
        exam = cursor.fetchone()
        if not exam:
            raise ValueError("Exam not found")
        cursor.execute("""
            SELECT q.id, q.question_text, q.options, q.correct_answer, q.difficulty, q.order_num,
                   ua.user_answer, ua.score, ua.ai_feedback
            FROM questions q
            LEFT JOIN user_answers ua ON q.id = ua.question_id AND ua.exam_id = %s
            WHERE q.exam_id = %s ORDER BY q.order_num
        """, (exam_id, exam_id))
        
        q_rows = cursor.fetchall()
        for q in q_rows:
            if q.get("options"):
                try:
                    q["options"] = json.loads(q["options"])
                except Exception:
                    q["options"] = []
            else:
                q["options"] = []
        exam["questions"] = q_rows
        return exam
    finally:
        cursor.close()
        conn.close()


def get_user_certificates(user_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM certificates WHERE user_id=%s ORDER BY issued_at DESC", (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def _get_owned_certificate(user_id: int, certificate_id: int) -> Dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT c.*, u.name AS account_name FROM certificates c
               JOIN users u ON u.id = c.user_id
               WHERE c.id = %s AND c.user_id = %s""",
            (certificate_id, user_id),
        )
        certificate = cursor.fetchone()
        if not certificate:
            raise ValueError("Certificate not found")
        return certificate
    finally:
        cursor.close()
        conn.close()


def regenerate_certificate_with_recipient_name(user_id: int, certificate_id: int, recipient_name: str) -> Dict:
    """Re-render one learner-owned certificate with a confirmed recipient name."""
    clean_name = " ".join((recipient_name or "").split())
    if len(clean_name) < 2 or len(clean_name) > 120:
        raise ValueError("Enter a full certificate name between 2 and 120 characters")

    certificate = _get_owned_certificate(user_id, certificate_id)
    file_path = generate_certificate(
        clean_name,
        certificate["topic"],
        float(certificate["score_percentage"]),
        certificate["certificate_number"],
        is_course_final=is_topic_course(certificate["topic"]),
    )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE certificates SET recipient_name = %s, file_path = %s WHERE id = %s AND user_id = %s",
            (clean_name, file_path, certificate_id, user_id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return {
        "certificate_id": certificate_id,
        "certificate_number": certificate["certificate_number"],
        "recipient_name": clean_name,
    }


def _normalise_email(recipient_email: str) -> str:
    from email_validator import EmailNotValidError, validate_email

    try:
        return validate_email(recipient_email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError("Enter a valid email address") from exc


def _send_smtp_message(message: EmailMessage, certificate_id: int | None = None) -> None:
    """Send a learner-facing message without exposing mail-provider details."""
    smtp_host = settings.SMTP_HOST
    if not smtp_host:
        raise ValueError("Certificate email delivery is temporarily unavailable. Please try again later.")
    try:
        with smtplib.SMTP(smtp_host, settings.SMTP_PORT, timeout=25) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        logger.exception("Certificate email delivery failed%s", f" for certificate {certificate_id}" if certificate_id else "")
        raise ValueError("Certificate email delivery is temporarily unavailable. Please try again later.") from exc


def _verification_hash(certificate_id: int, email: str, code: str) -> str:
    payload = f"{certificate_id}:{email}:{code}:{settings.SECRET_KEY}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def request_certificate_email_verification(user_id: int, certificate_id: int, recipient_email: str) -> Dict:
    """Email a short-lived one-time code before a certificate can be delivered."""
    email = _normalise_email(recipient_email)
    _get_owned_certificate(user_id, certificate_id)

    sender = settings.SMTP_FROM or settings.SMTP_USERNAME
    if not sender:
        raise ValueError("Certificate email delivery is temporarily unavailable. Please try again later.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    expiry = datetime.utcnow() + timedelta(minutes=settings.CERTIFICATE_EMAIL_VERIFICATION_TTL_MINUTES)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # One active code per recipient/certificate prevents multiple valid
        # codes from being used after a resend.
        cursor.execute(
            "DELETE FROM certificate_email_verifications WHERE user_id=%s AND certificate_id=%s AND email=%s",
            (user_id, certificate_id, email),
        )
        cursor.execute(
            """INSERT INTO certificate_email_verifications
               (user_id, certificate_id, email, code_hash, attempts, expires_at)
               VALUES (%s, %s, %s, %s, 0, %s)""",
            (user_id, certificate_id, email, _verification_hash(certificate_id, email, code), expiry),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    message = EmailMessage()
    message["Subject"] = "Verify your certificate email address"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Use this one-time code to confirm delivery of your official certificate:\n\n"
        f"{code}\n\n"
        f"This code expires in {settings.CERTIFICATE_EMAIL_VERIFICATION_TTL_MINUTES} minutes. "
        "If you did not request this, you can safely ignore this email."
    )
    try:
        _send_smtp_message(message, certificate_id)
    except ValueError:
        # Do not leave a usable code behind when the verification email was
        # not delivered.
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM certificate_email_verifications WHERE user_id=%s AND certificate_id=%s AND email=%s",
                (user_id, certificate_id, email),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        raise

    return {
        "certificate_id": certificate_id,
        "email": email,
        "expires_in_minutes": settings.CERTIFICATE_EMAIL_VERIFICATION_TTL_MINUTES,
    }


def email_certificate_pdf(user_id: int, certificate_id: int, recipient_email: str) -> Dict:
    """Send the current official PDF after recipient verification succeeds."""
    email = _normalise_email(recipient_email)
    certificate = _get_owned_certificate(user_id, certificate_id)
    file_path = certificate.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise ValueError("The certificate file is temporarily unavailable. Please try again shortly.")

    sender = settings.SMTP_FROM or settings.SMTP_USERNAME
    if not sender:
        raise ValueError("Certificate email delivery is temporarily unavailable. Please download the certificate instead or try again later.")

    recipient_name = certificate.get("recipient_name") or certificate.get("account_name") or "Learner"
    message = EmailMessage()
    message["Subject"] = f"Your {certificate['topic']} certificate"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Hello {recipient_name},\n\nCongratulations again. Your official {certificate['topic']} certificate is attached.\n\nCertificate number: {certificate['certificate_number']}\n"
    )
    with open(file_path, "rb") as pdf_file:
        message.add_attachment(
            pdf_file.read(),
            maintype="application",
            subtype="pdf",
            filename=f"certificate_{certificate['certificate_number']}.pdf",
        )

    _send_smtp_message(message, certificate_id)

    return {"certificate_id": certificate_id, "email": email}


def verify_certificate_email_and_deliver(
    user_id: int, certificate_id: int, recipient_email: str, code: str
) -> Dict:
    """Verify a one-time code and only then email the certificate PDF."""
    email = _normalise_email(recipient_email)
    clean_code = "".join((code or "").split())
    if not clean_code.isdigit() or len(clean_code) != 6:
        raise ValueError("Enter the six-digit verification code")
    _get_owned_certificate(user_id, certificate_id)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    verification_id = None
    try:
        cursor.execute(
            """SELECT id, code_hash, attempts, expires_at FROM certificate_email_verifications
               WHERE user_id=%s AND certificate_id=%s AND email=%s
               ORDER BY id DESC LIMIT 1""",
            (user_id, certificate_id, email),
        )
        verification = cursor.fetchone()
        if not verification or verification["expires_at"] < datetime.utcnow():
            raise ValueError("That verification code has expired. Please request a new code.")
        if verification["attempts"] >= settings.CERTIFICATE_EMAIL_VERIFICATION_MAX_ATTEMPTS:
            raise ValueError("Too many incorrect attempts. Please request a new verification code.")
        if not hmac.compare_digest(
            verification["code_hash"], _verification_hash(certificate_id, email, clean_code)
        ):
            cursor.execute(
                "UPDATE certificate_email_verifications SET attempts = attempts + 1 WHERE id=%s",
                (verification["id"],),
            )
            conn.commit()
            remaining = settings.CERTIFICATE_EMAIL_VERIFICATION_MAX_ATTEMPTS - verification["attempts"] - 1
            raise ValueError(f"That code is not correct. {remaining} attempt(s) remain.")
        verification_id = verification["id"]
    finally:
        cursor.close()
        conn.close()

    delivered = email_certificate_pdf(user_id, certificate_id, email)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM certificate_email_verifications WHERE id=%s", (verification_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return delivered


def get_leaderboard(topic: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if topic:
            cursor.execute("""
                SELECT u.name, e.topic, MAX(e.score_percentage) AS best_score, COUNT(e.id) AS attempts
                FROM exams e JOIN users u ON e.user_id = u.id
                WHERE e.topic = %s AND e.status IN ('passed','failed')
                GROUP BY u.id, e.topic ORDER BY best_score DESC LIMIT 10
            """, (topic,))
        else:
            cursor.execute("""
                SELECT u.name, MAX(e.score_percentage) AS best_score,
                       COUNT(DISTINCT CASE WHEN e.status='passed' THEN e.topic END) AS topics_passed
                FROM exams e JOIN users u ON e.user_id = u.id
                GROUP BY u.id ORDER BY best_score DESC, topics_passed DESC LIMIT 10
            """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
