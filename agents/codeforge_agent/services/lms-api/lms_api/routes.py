from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_student
from .errors import ApiError


coding = Blueprint("coding", __name__, url_prefix="/api/coding")


def repo():
    return current_app.extensions["repository"]


@coding.get("/dashboard")
@require_student
def dashboard():
    data = repo().dashboard(g.student["id"])
    return jsonify({"student": g.student, **data, "progress": repo().progress_summary(g.student["id"])})


@coding.get("/courses")
@require_student
def courses():
    return jsonify({"courses": repo().list_courses(g.student["id"])})


@coding.get("/courses/<course_slug>")
@require_student
def course(course_slug):
    selected, technologies = repo().list_technologies(course_slug)
    return jsonify({"course": selected, "technologies": technologies, "continue": repo().continue_destination(g.student["id"])})


@coding.get("/courses/<course_slug>/technologies")
@require_student
def technologies(course_slug):
    selected, items = repo().list_technologies(course_slug)
    return jsonify({"course": selected, "technologies": items})


@coding.get("/courses/<course_slug>/technologies/<technology_slug>/topics")
@require_student
def topics(course_slug, technology_slug):
    selected_course, selected_technology, items = repo().list_topics(course_slug, technology_slug, g.student["id"])
    return jsonify({"course": selected_course, "technology": selected_technology, "topics": items})


@coding.get("/courses/<course_slug>/technologies/<technology_slug>/topics/<topic_slug>")
@require_student
def topic(course_slug, technology_slug, topic_slug):
    selected_course, selected_technology, selected_topic = repo().get_topic(course_slug, technology_slug, topic_slug)
    return jsonify({"course": selected_course, "technology": selected_technology, "topic": selected_topic})


@coding.get("/courses/<course_slug>/technologies/<technology_slug>/topics/<topic_slug>/problems")
@require_student
def problems(course_slug, technology_slug, topic_slug):
    selected_course, selected_technology, selected_topic, items = repo().list_problems(
        g.student["id"], course_slug, technology_slug, topic_slug
    )
    return jsonify({"course": selected_course, "technology": selected_technology, "topic": selected_topic, "problems": items})


@coding.get("/courses/<course_slug>/technologies/<technology_slug>/topics/<topic_slug>/problems/<problem_slug>")
@require_student
def problem(course_slug, technology_slug, topic_slug, problem_slug):
    selected_course, selected_technology, selected_topic, selected_problem = repo().get_problem(
        g.student["id"], course_slug, technology_slug, topic_slug, problem_slug
    )
    return jsonify({"course": selected_course, "technology": selected_technology, "topic": selected_topic, "problem": selected_problem})


@coding.post("/problems/<int:problem_id>/run")
@require_student
def run_problem(problem_id):
    payload = _json()
    outcome = current_app.extensions["evaluation"].evaluate(g.student["id"], problem_id, payload.get("sourceCode"), "run")
    return jsonify(outcome), 201


@coding.post("/problems/<int:problem_id>/submit")
@require_student
def submit_problem(problem_id):
    payload = _json()
    outcome = current_app.extensions["evaluation"].evaluate(g.student["id"], problem_id, payload.get("sourceCode"), "submit")
    return jsonify(outcome), 201


@coding.post("/problems/<int:problem_id>/tutor")
@require_student
def tutor(problem_id):
    payload = _json()
    submission_id = payload.get("submissionId")
    hint_level = payload.get("hintLevel", 1)
    if not isinstance(submission_id, int) or not isinstance(hint_level, int) or not 1 <= hint_level <= 3:
        raise ApiError("Tutor request is invalid.", 400, "invalid_tutor_request")
    problem_row = repo().problem_for_evaluation(g.student["id"], problem_id)
    submission = repo().get_submission(g.student["id"], problem_id, submission_id)
    guidance = current_app.extensions["tutor"].explain(problem_row, submission, hint_level)
    repo().save_tutor_interaction(g.student["id"], problem_id, submission_id, guidance["errorCategory"], guidance["explanation"])
    return jsonify({"guidance": guidance})


@coding.post("/activity")
@require_student
def activity():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("A JSON request body is required.", 400, "invalid_json")
    course_slug = _slug(payload.get("courseSlug"), "courseSlug")
    technology_slug = _optional_slug(payload.get("technologySlug"), "technologySlug")
    topic_slug = _optional_slug(payload.get("topicSlug"), "topicSlug")
    result = repo().record_activity(g.student["id"], course_slug, technology_slug, topic_slug)
    return jsonify({"activity": result}), 201


@coding.get("/continue")
@require_student
def continue_practice():
    return jsonify({"continue": repo().continue_destination(g.student["id"])})


@coding.get("/profile")
@require_student
def profile():
    return jsonify({"profile": repo().get_profile(g.student["id"])})


@coding.patch("/profile")
@require_student
def update_profile():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("A JSON request body is required.", 400, "invalid_json")
    display_name = str(payload.get("displayName", "")).strip()
    bio = str(payload.get("bio", "")).strip()
    timezone = str(payload.get("timezone", "")).strip()
    if not 2 <= len(display_name) <= 120:
        raise ApiError("Display name must contain 2 to 120 characters.", 400, "invalid_display_name")
    if len(bio) > 500:
        raise ApiError("Bio must contain at most 500 characters.", 400, "invalid_bio")
    if not 1 <= len(timezone) <= 64 or "/" not in timezone:
        raise ApiError("Choose a valid IANA timezone.", 400, "invalid_timezone")
    return jsonify({"profile": repo().update_profile(g.student["id"], display_name, bio, timezone)})


def _slug(value, field):
    if not isinstance(value, str) or not value or len(value) > 120:
        raise ApiError(f"{field} is invalid.", 400, "invalid_parameter")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value):
        raise ApiError(f"{field} is invalid.", 400, "invalid_parameter")
    return value


def _optional_slug(value, field):
    return None if value is None else _slug(value, field)


def _json():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("A JSON request body is required.", 400, "invalid_json")
    return payload
