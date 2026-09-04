"""Common Strategy F contract (`POST /api/invoke`) used by the
registry-resolved orchestrator gateway.

The orchestrator gateway forwards only Content-Type + the raw request body —
it never signs anything — so this cannot reuse require_service/require_student,
which demand the X-CodeForge-* HMAC envelope on every request. Instead every
action (other than health/ensure_session) requires an unguessable, revocable,
expiring `sessionToken` carried in the JSON payload, validated exactly the
way require_student validates the X-CodeForge-Session header
(repository.student_for_session). The pre-existing /api/auth/* and
/api/coding/* routes, and their HMAC requirement, are completely untouched.
"""

from flask import Blueprint, current_app, jsonify, request

from .errors import ApiError

invoke_bp = Blueprint("invoke", __name__)


def repo():
    return current_app.extensions["repository"]


def _student_from_payload(payload):
    token = payload.get("sessionToken")
    if not isinstance(token, str) or not token:
        raise ApiError("Authentication is required.", 401, "unauthenticated")
    student = repo().student_for_session(token)
    if not student:
        raise ApiError("Your session has expired. Please sign in again.", 401, "invalid_session")
    if not student["is_active"]:
        raise ApiError("This student account is inactive.", 403, "inactive_student")
    return student


def _int(value, field):
    if isinstance(value, bool):
        raise ApiError(f"{field} is invalid.", 400, "invalid_parameter")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} is invalid.", 400, "invalid_parameter") from None


@invoke_bp.post("/api/invoke")
def invoke():
    if not current_app.config["CODING_PRACTICE_ENABLED"]:
        raise ApiError("Coding Practice is currently unavailable.", 404, "feature_disabled")

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("A JSON request body is required.", 400, "invalid_json")
    action = body.get("action")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if action == "health":
        return jsonify({"status": "ok", "agent_name": "codeforge_agent"})

    if action == "ensure_session":
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        if not name or not email:
            raise ApiError("name and email are required.", 400, "invalid_parameter")
        student, token, expires_at = repo().ensure_session(f"digidara:{email}", email, name)
        return jsonify({"student": student, "sessionToken": token, "expiresAt": expires_at})

    if action == "usage_summary":
        # Platform-wide metric, not scoped to a student — no session required,
        # same as health/ensure_session above.
        return jsonify(repo().get_llm_usage_summary())

    if action == "list_languages":
        # Static reference data from Judge0 itself — no session required.
        languages = current_app.extensions["evaluation"].judge.languages()
        return jsonify({"languages": languages})

    if action == "run_playground":
        source_code = payload.get("sourceCode")
        language_id = payload.get("languageId")
        stdin_text = payload.get("stdin") or ""
        if not isinstance(source_code, str) or not source_code.strip() or len(source_code) > 50000:
            raise ApiError("Source code must contain 1 to 50,000 characters.", 400, "invalid_source")
        if not isinstance(language_id, int):
            raise ApiError("languageId is required.", 400, "invalid_parameter")
        result = current_app.extensions["evaluation"].judge.execute(
            source_code, language_id, stdin_text, expected_output=None
        )
        return jsonify(result)
    # Every remaining action requires a real, previously-issued session.
    student = _student_from_payload(payload)

    if action == "dashboard":
        data = repo().dashboard(student["id"])
        return jsonify({"student": student, **data, "progress": repo().progress_summary(student["id"])})

    if action == "list_courses":
        return jsonify({"courses": repo().list_courses(student["id"])})

    if action == "list_technologies":
        selected, technologies = repo().list_technologies(payload.get("course_slug"))
        return jsonify({
            "course": selected,
            "technologies": technologies,
            "continue": repo().continue_destination(student["id"]),
        })

    if action == "list_topics":
        selected_course, selected_technology, items = repo().list_topics(
            payload.get("course_slug"), payload.get("technology_slug"), student["id"]
        )
        return jsonify({"course": selected_course, "technology": selected_technology, "topics": items})

    if action == "list_problems":
        selected_course, selected_technology, selected_topic, items = repo().list_problems(
            student["id"], payload.get("course_slug"), payload.get("technology_slug"), payload.get("topic_slug")
        )
        return jsonify({
            "course": selected_course,
            "technology": selected_technology,
            "topic": selected_topic,
            "problems": items,
        })

    if action == "get_problem":
        selected_course, selected_technology, selected_topic, selected_problem = repo().get_problem(
            student["id"],
            payload.get("course_slug"),
            payload.get("technology_slug"),
            payload.get("topic_slug"),
            payload.get("problem_slug"),
        )
        return jsonify({
            "course": selected_course,
            "technology": selected_technology,
            "topic": selected_topic,
            "problem": selected_problem,
        })

    if action in ("run_problem", "submit_problem"):
        problem_id = _int(payload.get("problem_id"), "problem_id")
        mode = "run" if action == "run_problem" else "submit"
        outcome = current_app.extensions["evaluation"].evaluate(
            student["id"], problem_id, payload.get("sourceCode"), mode
        )
        return jsonify(outcome), 201

    if action == "run_playground":
        source_code = payload.get("sourceCode")
        language_id = payload.get("languageId")
        stdin_text = payload.get("stdin") or ""
        if not isinstance(source_code, str) or not source_code.strip() or len(source_code) > 50000:
            raise ApiError("Source code must contain 1 to 50,000 characters.", 400, "invalid_source")
        if not isinstance(language_id, int):
            raise ApiError("languageId is required.", 400, "invalid_parameter")
        result = current_app.extensions["evaluation"].judge.execute(
            source_code, language_id, stdin_text, expected_output=None
        )
        return jsonify(result)

    if action == "tutor":
        problem_id = _int(payload.get("problem_id"), "problem_id")
        submission_id = payload.get("submissionId")
        hint_level = payload.get("hintLevel", 2)
        if not isinstance(submission_id, int) or not isinstance(hint_level, int) or not 1 <= hint_level <= 3:
            raise ApiError("Tutor request is invalid.", 400, "invalid_tutor_request")
        problem_row = repo().problem_for_evaluation(student["id"], problem_id)
        submission = repo().get_submission(student["id"], problem_id, submission_id)
        guidance = current_app.extensions["tutor"].explain(problem_row, submission, hint_level)
        repo().save_tutor_interaction(
            student["id"], problem_id, submission_id, guidance["errorCategory"], guidance["explanation"]
        )
        return jsonify({"guidance": guidance})

    raise ApiError(f"Unknown action: {action!r}", 400, "unknown_action")
