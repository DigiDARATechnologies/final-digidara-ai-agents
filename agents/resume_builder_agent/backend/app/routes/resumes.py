from datetime import date, datetime, timezone

from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError

from app.errors import database_error_response
from app.extensions import db
from app.models import (
    Certification,
    AtsAnalysis,
    Achievement,
    Education,
    Experience,
    PersonalInfo,
    Project,
    Publication,
    Resume,
    Skill,
    User,
    Language,
)
from app.services.pdf_export import VALID_TEMPLATES, render_resume_pdf
from app.services.import_review import (
    ImportValidationError,
    analyze_resume_text,
    map_import_to_resume_payload,
    score_resume,
    validate_import_file,
)
from app.security import dev_header_allowed, in_invoke_reentry, rate_limit, session_user_id
from app.template_catalog import LEGACY_TEMPLATE_ALIASES, TEMPLATE_BY_ID, TEMPLATE_METADATA

resumes_bp = Blueprint("resumes", __name__)
VALID_TEMPLATE_CHOICES = VALID_TEMPLATES | set(LEGACY_TEMPLATE_ALIASES)
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}$")
VALID_RESUME_STATUSES = {"draft", "completed", "archived"}
MAX_SECTION_ITEMS = 50
MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
MONTH_LABELS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def success_response(data=None, message="OK", status_code=200):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def error_response(message, status_code=400, details=None):
    payload = {"success": False, "message": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def get_request_user_id(payload=None):
    payload = payload or {}
    verified_session_user = session_user_id()
    if verified_session_user:
        return verified_session_user

    # The internal adapter may supply identity; direct browser headers require
    # explicit development mode. Network isolation alone is not authentication.
    header_value = request.headers.get("X-User-Id")
    if isinstance(header_value, str) and (dev_header_allowed() or in_invoke_reentry()):
        header_value = header_value.strip()
        if USER_ID_PATTERN.fullmatch(header_value):
            return header_value

    if not dev_header_allowed():
        return None
    value = request.args.get("user_id") or payload.get("user_id")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if USER_ID_PATTERN.fullmatch(value) else None


def user_can_access_resume(resume, user_id):
    return bool(user_id) and resume.user_id == user_id


def validate_user_id(value):
    if not isinstance(value, str) or not USER_ID_PATTERN.fullmatch(value.strip()):
        raise ValueError(
            "user_id must be 1-64 characters using letters, numbers, '.', '_', ':', '@', or '-'."
        )
    return value.strip()


def clean_text(value, field, max_length, required=False):
    if value is None:
        if required:
            raise ValueError(f"Missing required field: {field}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Missing required field: {field}")
    if len(value) > max_length:
        raise ValueError(f"{field} must not exceed {max_length} characters")
    return value or None


def clean_list(value, field, max_items=MAX_SECTION_ITEMS):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) > max_items:
        raise ValueError(f"{field} must contain at most {max_items} items")
    return value


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text.lower() in {"present", "current", "ongoing", "now"}:
        return None
    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1)
    month_year = parse_month_year(text)
    if month_year:
        return month_year
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD or Month YYYY.")


def parse_month_year(value):
    parts = value.replace(",", " ").split()
    if len(parts) != 2:
        return None

    month = MONTH_NAMES.get(parts[0].lower())
    year = parts[1]
    if not month or not (len(year) == 4 and year.isdigit()):
        return None
    return date(int(year), month, 1)


def parse_education_year(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1)
    return parse_date(text)


def clean_decimal(value, field, max_length=20):
    value = clean_text(value, field, max_length)
    if value is None:
        return None
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError(f"{field} must contain decimal numbers only")
    return value


def format_date(value):
    if not value:
        return None
    if value.day == 1:
        return f"{MONTH_LABELS[value.month]} {value.year}"
    return value.isoformat()


def format_year(value):
    return str(value.year) if value else None


def format_datetime(value):
    return value.isoformat() if value else None


def require_fields(payload, fields):
    missing = [field for field in fields if not payload.get(field)]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")


def serialize_resume_summary(resume):
    completion_percentage = calculate_completion_percentage(resume)
    return {
        "id": resume.id,
        "user_id": resume.user_id,
        "title": resume.title,
        "target_role": resume.target_role,
        "experience_level": resume.experience_level,
        "template_choice": normalize_template_choice(resume.template_choice),
        "status": effective_resume_status(resume, completion_percentage),
        "summary": resume.summary,
        "profile_photo": resume.profile_photo,
        "declaration": resume.declaration,
        "ats_score": resume.ats_score,
        "job_match_score": resume.job_match_score,
        "download_count": resume.download_count or 0,
        "last_downloaded_at": format_datetime(resume.last_downloaded_at),
        "last_analyzed_at": format_datetime(resume.last_analyzed_at),
        "completion_percentage": completion_percentage,
        "created_at": format_datetime(resume.created_at),
        "updated_at": format_datetime(resume.updated_at),
    }


def serialize_resume(resume):
    data = serialize_resume_summary(resume)
    data.update(
        {
            "personal_info": serialize_personal_info(resume.personal_info),
            "education": [serialize_education(item) for item in resume.education],
            "experience": [serialize_experience(item) for item in resume.experience],
            "skills": [serialize_skill(item) for item in resume.skills],
            "certifications": [
                serialize_certification(item) for item in resume.certifications
            ],
            "projects": [serialize_project(item) for item in resume.projects],
            "publications": [serialize_publication(item) for item in resume.publications],
            "languages": [serialize_language(item) for item in resume.languages],
            "achievements": [serialize_achievement(item) for item in resume.achievements],
        }
    )
    return data


def serialize_personal_info(item):
    if not item:
        return None
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "name": item.name,
        "email": item.email,
        "phone": item.phone,
        "location": item.location,
        "links": item.links or [],
    }


def serialize_education(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "school": item.school,
        "degree": item.degree,
        "field": item.field,
        "start_date": format_year(item.start_date),
        "end_date": format_year(item.end_date),
        "cgpa": item.cgpa,
    }


def serialize_experience(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "company": item.company,
        "role": item.role,
        "start_date": format_date(item.start_date),
        "end_date": "Present" if item.is_current else format_date(item.end_date),
        "is_current": bool(item.is_current),
        "raw_input": item.raw_input,
        "ai_generated_bullets": item.ai_generated_bullets or [],
    }


def serialize_skill(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "skill_name": item.skill_name,
    }


def serialize_certification(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "name": item.name,
        "issuer": item.issuer,
        "date": format_date(item.date),
    }


def serialize_project(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "title": item.title,
        "description": item.description,
        "ai_generated_bullets": item.ai_generated_bullets or [],
    }


def serialize_publication(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "title": item.title,
        "description": item.description,
        "date": format_date(item.date),
    }


def serialize_language(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "language_name": item.language_name,
        "proficiency": item.proficiency,
    }


def serialize_achievement(item):
    return {
        "id": item.id,
        "resume_id": item.resume_id,
        "title": item.title,
        "description": item.description,
        "date": format_date(item.date),
    }


def get_resume_or_404(resume_id):
    return db.session.get(Resume, resume_id)


def normalize_template_choice(template_choice):
    template = (template_choice or "steady-form").lower()
    return LEGACY_TEMPLATE_ALIASES.get(template, template)


def extract_target_role(payload):
    for key in ("target_role", "targetRole", "target_job_title", "targetJobTitle", "role", "jobTitle"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value:
            return value
    return None


def extract_experience_level(payload):
    value = payload.get("experience_level", payload.get("experienceLevel"))
    if value is None or value == "":
        return None
    value = clean_text(value, "experience_level", 20).lower()
    if value not in {"fresher", "experienced"}:
        raise ValueError("experience_level must be fresher or experienced")
    return value


def calculate_completion_percentage(resume):
    checks = [
        bool(resume.title and resume.title != "Untitled Resume"),
        bool(resume.target_role),
        bool(resume.personal_info and resume.personal_info.name and resume.personal_info.email),
        bool(resume.summary),
        bool(resume.skills),
        bool(resume.experience),
        bool(resume.education),
        bool(resume.publications),
    ]
    return round((sum(checks) / len(checks)) * 100)


def effective_resume_status(resume, completion_percentage=None):
    if resume.status == "archived":
        return "archived"
    completion = (
        calculate_completion_percentage(resume)
        if completion_percentage is None
        else completion_percentage
    )
    return "completed" if completion >= 100 else "draft"


def sync_resume_status_with_completion(resume):
    if resume.status == "archived":
        return
    resume.status = effective_resume_status(resume)


def apply_resume_payload(resume, payload):
    if "title" in payload:
        resume.title = clean_text(payload["title"], "title", 255) or "Untitled Resume"
    target_role = extract_target_role(payload)
    if target_role is not None:
        resume.target_role = clean_text(target_role, "target_role", 255)
    if "experience_level" in payload or "experienceLevel" in payload:
        resume.experience_level = extract_experience_level(payload)
    if "status" in payload:
        status = clean_text(payload.get("status"), "status", 30) or "draft"
        if status not in VALID_RESUME_STATUSES:
            raise ValueError("status must be draft, completed, or archived")
        resume.status = status
    if "template_choice" in payload:
        template_choice = normalize_template_choice(payload.get("template_choice"))
        if template_choice not in VALID_TEMPLATES:
            raise ValueError(
                f"Invalid template_choice. Use one of: {', '.join(sorted(VALID_TEMPLATES))}."
            )
        resume.template_choice = template_choice
    if "summary" in payload:
        resume.summary = clean_text(payload.get("summary"), "summary", 12000)
    if "profile_photo" in payload:
        resume.profile_photo = clean_text(payload.get("profile_photo"), "profile_photo", 500)
    if "declaration" in payload:
        resume.declaration = clean_text(payload.get("declaration"), "declaration", 4000)

    if "personal_info" in payload:
        personal_info = payload["personal_info"] or {}
        apply_personal_info_payload(
            resume,
            personal_info if has_content(personal_info) else None,
        )
    if "education" in payload:
        resume.education = [
            build_education(item)
            for item in clean_list(payload["education"], "education")
            if has_content(item)
        ]
    if "experience" in payload:
        resume.experience = [
            build_experience(item)
            for item in clean_list(payload["experience"], "experience")
            if has_content(item)
        ]
    if "skills" in payload:
        resume.skills = [
            build_skill(item)
            for item in clean_list(payload["skills"], "skills")
            if has_content(item)
        ]
    if "certifications" in payload:
        resume.certifications = [
            build_certification(item)
            for item in clean_list(payload["certifications"], "certifications")
            if has_content(item)
        ]
    if "projects" in payload:
        resume.projects = [
            build_project(item)
            for item in clean_list(payload["projects"], "projects")
            if has_content(item)
        ]
    if "publications" in payload:
        resume.publications = [
            build_publication(item)
            for item in clean_list(payload["publications"], "publications")
            if has_content(item)
        ]
    if "languages" in payload:
        resume.languages = [
            build_language(item)
            for item in clean_list(payload["languages"], "languages")
            if has_content(item)
        ]
    if "achievements" in payload:
        resume.achievements = [
            build_achievement(item)
            for item in clean_list(payload["achievements"], "achievements")
            if has_content(item)
        ]

    sync_resume_status_with_completion(resume)


def has_content(item):
    if isinstance(item, str):
        return bool(item.strip())
    if not isinstance(item, dict):
        return False
    return any(
        value.strip() if isinstance(value, str) else value
        for key, value in item.items()
        if key not in {"id", "resume_id"}
    )


def build_personal_info(payload):
    payload = payload or {}
    require_fields(payload, ["name", "email"])
    links = clean_list(payload.get("links"), "personal_info.links", 10)
    return PersonalInfo(
        name=clean_text(payload["name"], "personal_info.name", 255, required=True),
        email=clean_text(payload["email"], "personal_info.email", 255, required=True),
        phone=clean_text(payload.get("phone"), "personal_info.phone", 50),
        location=clean_text(payload.get("location"), "personal_info.location", 255),
        links=[clean_text(link, "personal_info.links", 500, required=True) for link in links],
    )


def apply_personal_info_payload(resume, payload):
    if payload is None:
        resume.personal_info = None
        return

    require_fields(payload, ["name", "email"])
    if not resume.personal_info:
        resume.personal_info = build_personal_info(payload)
        return

    links = clean_list(payload.get("links"), "personal_info.links", 10)
    resume.personal_info.name = clean_text(payload["name"], "personal_info.name", 255, required=True)
    resume.personal_info.email = clean_text(payload["email"], "personal_info.email", 255, required=True)
    resume.personal_info.phone = clean_text(payload.get("phone"), "personal_info.phone", 50)
    resume.personal_info.location = clean_text(payload.get("location"), "personal_info.location", 255)
    resume.personal_info.links = [
        clean_text(link, "personal_info.links", 500, required=True) for link in links
    ]


def build_education(payload):
    require_fields(payload, ["school"])
    return Education(
        school=clean_text(payload["school"], "education.school", 255, required=True),
        degree=clean_text(payload.get("degree"), "education.degree", 255),
        field=clean_text(payload.get("field"), "education.field", 255),
        start_date=parse_education_year(payload.get("start_date")),
        end_date=parse_education_year(payload.get("end_date")),
        cgpa=clean_decimal(payload.get("cgpa"), "education.cgpa", 20),
    )


def build_experience(payload):
    require_fields(payload, ["company", "role"])
    bullets = clean_list(payload.get("ai_generated_bullets"), "experience.ai_generated_bullets", 20)
    is_current = bool(payload.get("is_current", payload.get("isCurrent", False))) or str(payload.get("end_date") or "").strip().lower() in {"present", "current", "ongoing", "now"}
    return Experience(
        company=clean_text(payload["company"], "experience.company", 255, required=True),
        role=clean_text(payload["role"], "experience.role", 255, required=True),
        start_date=parse_date(payload.get("start_date")),
        end_date=None if is_current else parse_date(payload.get("end_date")),
        is_current=is_current,
        raw_input=clean_text(payload.get("raw_input"), "experience.raw_input", 12000),
        ai_generated_bullets=[
            clean_text(bullet, "experience.ai_generated_bullets", 1500, required=True)
            for bullet in bullets
        ],
    )


def build_skill(payload):
    if isinstance(payload, str):
        payload = {"skill_name": payload}
    require_fields(payload, ["skill_name"])
    return Skill(skill_name=clean_text(payload["skill_name"], "skills.skill_name", 150, required=True))


def build_certification(payload):
    require_fields(payload, ["name"])
    return Certification(
        name=clean_text(payload["name"], "certifications.name", 255, required=True),
        issuer=clean_text(payload.get("issuer"), "certifications.issuer", 255),
        date=parse_date(payload.get("date")),
    )


def build_project(payload):
    require_fields(payload, ["title"])
    bullets = clean_list(payload.get("ai_generated_bullets"), "projects.ai_generated_bullets", 20)
    return Project(
        title=clean_text(payload["title"], "projects.title", 255, required=True),
        description=clean_text(payload.get("description"), "projects.description", 12000),
        ai_generated_bullets=[
            clean_text(bullet, "projects.ai_generated_bullets", 1500, required=True)
            for bullet in bullets
        ],
    )


def build_publication(payload):
    require_fields(payload, ["title"])
    return Publication(
        title=clean_text(payload["title"], "publications.title", 255, required=True),
        description=clean_text(payload.get("description"), "publications.description", 12000),
        date=parse_date(payload.get("date")),
    )


def build_language(payload):
    require_fields(payload, ["language_name"])
    return Language(
        language_name=clean_text(payload["language_name"], "languages.language_name", 100, required=True),
        proficiency=clean_text(payload.get("proficiency"), "languages.proficiency", 50),
    )


def build_achievement(payload):
    require_fields(payload, ["title"])
    return Achievement(
        title=clean_text(payload["title"], "achievements.title", 255, required=True),
        description=clean_text(payload.get("description"), "achievements.description", 12000),
        date=parse_date(payload.get("date")),
    )


@resumes_bp.post("/resume")
@resumes_bp.post("/resumes")
@rate_limit(30)
def create_resume():
    payload = request.get_json(silent=True) or {}
    try:
        user_id = get_request_user_id(payload)
        if not user_id:
            raise ValueError("Missing required user_id or secure session")
        user_id = validate_user_id(user_id)
        title = clean_text(payload.get("title"), "title", 255) or "Untitled Resume"
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id)
            db.session.add(user)
            db.session.flush()

        resume = Resume(
            user_id=user_id,
            title=title,
            target_role=extract_target_role(payload),
            experience_level=extract_experience_level(payload),
            template_choice="steady-form",
            summary=payload.get("summary"),
        )
        apply_resume_payload(resume, payload)
        db.session.add(resume)
        db.session.commit()
        return success_response(
            serialize_resume(resume),
            message="Resume created",
            status_code=201,
        )
    except ValueError as exc:
        db.session.rollback()
        return error_response(str(exc), 400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


@resumes_bp.get("/resume/<int:resume_id>")
@resumes_bp.get("/resumes/<int:resume_id>")
def get_resume(resume_id):
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not resume or not user_can_access_resume(resume, get_request_user_id()):
        return error_response("Resume not found", 404)
    return success_response(serialize_resume(resume), message="Resume fetched")


@resumes_bp.put("/resume/<int:resume_id>")
@resumes_bp.put("/resumes/<int:resume_id>")
@resumes_bp.patch("/resumes/<int:resume_id>")
@rate_limit(60)
def update_resume(resume_id):
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    payload = request.get_json(silent=True) or {}
    if not resume or not user_can_access_resume(resume, get_request_user_id(payload)):
        return error_response("Resume not found", 404)

    try:
        if "user_id" in payload and payload["user_id"] != resume.user_id:
            raise ValueError("Resume owner cannot be changed")

        apply_resume_payload(resume, payload)
        db.session.commit()
        return success_response(serialize_resume(resume), message="Resume updated")
    except ValueError as exc:
        db.session.rollback()
        return error_response(str(exc), 400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


@resumes_bp.post("/resume/<int:resume_id>/photo")
@rate_limit(20)
def upload_resume_photo(resume_id):
    resume = get_resume_or_404(resume_id)
    if not resume or not user_can_access_resume(resume, get_request_user_id()):
        return error_response("Resume not found", 404)
    uploaded = request.files.get("photo")
    if not uploaded or not uploaded.filename:
        return error_response("Attach a PNG, JPEG, or WebP photo.", 400)
    try:
        from PIL import Image
        image = Image.open(uploaded.stream)
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Photo must be a PNG, JPEG, or WebP image")
        image = image.convert("RGB")
        edge = min(image.size)
        image = image.crop(((image.width-edge)//2, (image.height-edge)//2, (image.width+edge)//2, (image.height+edge)//2))
        image.thumbnail((600, 600))
        upload_dir = Path(__file__).resolve().parents[2] / "uploads" / "resume_photos"
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{resume.id}-{uuid4().hex}.jpg"
        image.save(upload_dir / filename, "JPEG", quality=88, optimize=True)
        resume.profile_photo = filename
        db.session.commit()
        return success_response(serialize_resume(resume), message="Profile photo uploaded")
    except (OSError, ValueError) as exc:
        return error_response(str(exc) or "Invalid image file", 400)


@resumes_bp.get("/resume/<int:resume_id>/photo")
def get_resume_photo(resume_id):
    resume = get_resume_or_404(resume_id)
    if not resume or not resume.profile_photo or not user_can_access_resume(resume, get_request_user_id()):
        return error_response("Profile photo not found", 404)
    upload_dir = Path(__file__).resolve().parents[2] / "uploads" / "resume_photos"
    return send_from_directory(upload_dir, secure_filename(resume.profile_photo), mimetype="image/jpeg")


@resumes_bp.delete("/resume/<int:resume_id>")
@resumes_bp.delete("/resumes/<int:resume_id>")
@rate_limit(30)
def delete_resume(resume_id):
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not resume or not user_can_access_resume(resume, get_request_user_id()):
        return error_response("Resume not found", 404)

    try:
        db.session.delete(resume)
        db.session.commit()
        return success_response(message="Resume deleted")
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


@resumes_bp.get("/resumes")
def list_resumes():
    raw_user_id = get_request_user_id()
    if not raw_user_id:
        return error_response("Missing required user_id or secure session", 400)
    try:
        user_id = validate_user_id(raw_user_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    try:
        query = Resume.query.filter_by(user_id=user_id)

        status = request.args.get("status")

        template = request.args.get("template")
        if template and template != "all":
            normalized_template = normalize_template_choice(template)
            legacy_aliases = [
                old_template
                for old_template, current_template in LEGACY_TEMPLATE_ALIASES.items()
                if current_template == normalized_template
            ]
            query = query.filter(
                Resume.template_choice.in_([normalized_template, *legacy_aliases])
            )

        sort = request.args.get("sort") or "updated"
        if sort == "created":
            query = query.order_by(Resume.created_at.desc(), Resume.id.desc())
        elif sort == "title":
            query = query.order_by(Resume.title.asc(), Resume.updated_at.desc())
        else:
            query = query.order_by(Resume.updated_at.desc(), Resume.created_at.desc())

        resumes = query.all()
        if status and status != "all":
            if status not in VALID_RESUME_STATUSES:
                return error_response("status must be draft, completed, or archived", 400)
            resumes = [
                resume
                for resume in resumes
                if effective_resume_status(resume) == status
            ]
    except SQLAlchemyError as exc:
        return database_error_response(exc)

    return success_response(
        [serialize_resume_summary(resume) for resume in resumes],
        message="Resumes fetched",
    )


@resumes_bp.post("/resume/<int:resume_id>/duplicate")
@resumes_bp.post("/resumes/<int:resume_id>/duplicate")
@rate_limit(20)
def duplicate_resume(resume_id):
    payload = request.get_json(silent=True) or {}
    user_id = get_request_user_id(payload)
    if not user_id:
        return error_response("Missing required user context", 400)

    try:
        source = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not source or not user_can_access_resume(source, user_id):
        return error_response("Resume not found", 404)

    try:
        title = payload.get("title") or f"{source.title} Copy"
        duplicate = Resume(
            user_id=user_id,
            title=title,
            target_role=source.target_role,
            experience_level=source.experience_level,
            template_choice=source.template_choice,
            summary=source.summary,
            declaration=source.declaration,
        )
        duplicate.personal_info = (
            build_personal_info(serialize_personal_info(source.personal_info))
            if source.personal_info
            else None
        )
        duplicate.education = [
            build_education(serialize_education(item)) for item in source.education
        ]
        duplicate.experience = [
            build_experience(serialize_experience(item)) for item in source.experience
        ]
        duplicate.skills = [build_skill(serialize_skill(item)) for item in source.skills]
        duplicate.certifications = [
            build_certification(serialize_certification(item))
            for item in source.certifications
        ]
        duplicate.projects = [
            build_project(serialize_project(item)) for item in source.projects
        ]
        duplicate.publications = [
            build_publication(serialize_publication(item)) for item in source.publications
        ]
        duplicate.languages = [
            build_language(serialize_language(item)) for item in source.languages
        ]
        duplicate.achievements = [
            build_achievement(serialize_achievement(item)) for item in source.achievements
        ]
        db.session.add(duplicate)
        db.session.commit()
        return success_response(
            serialize_resume(duplicate),
            message="Resume duplicated",
            status_code=201,
        )
    except ValueError as exc:
        db.session.rollback()
        return error_response(str(exc), 400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


@resumes_bp.post("/resume/<int:resume_id>/export")
@resumes_bp.post("/resumes/<int:resume_id>/download")
@rate_limit(30)
def export_resume(resume_id):
    payload = request.get_json(silent=True) or {}
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not resume or not user_can_access_resume(resume, get_request_user_id(payload)):
        return error_response("Resume not found", 404)

    template_choice = (
        payload.get("template_choice")
        or payload.get("templateId")
        or resume.template_choice
        or "steady-form"
    )
    template_choice = normalize_template_choice(template_choice)
    if template_choice not in VALID_TEMPLATES:
        return error_response(
            f"template_choice must be one of: {', '.join(sorted(VALID_TEMPLATES))}",
            400,
        )

    try:
        pdf_bytes = render_resume_pdf(serialize_resume(resume), template_choice)
        resume.last_downloaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
        resume.download_count = (resume.download_count or 0) + 1
        db.session.commit()
    except RuntimeError as exc:
        db.session.rollback()
        return error_response(str(exc), 500)
    except Exception:
        db.session.rollback()
        # Keep the client response safe while retaining the server-side cause
        # needed to diagnose export failures through the gateway.
        current_app.logger.exception("PDF export failed for resume_id=%s", resume_id)
        return error_response("PDF export failed", 500)

    filename = f"{build_resume_filename(resume, template_choice)}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@resumes_bp.post("/resumes/preview")
# The editor debounces PDF previews, but template browsing and normal typing
# can still exceed one request per second. Keep abuse protection while allowing
# a responsive local editing session.
@rate_limit(240)
def preview_resume_pdf():
    """Render the live preview with the exact engine used for downloads."""
    payload = request.get_json(silent=True) or {}
    user_id = get_request_user_id(payload)
    if not user_id:
        return error_response("Missing or invalid user context", 400)

    resume_data = payload.get("resume")
    if not isinstance(resume_data, dict):
        return error_response("Missing required field: resume", 400)
    if resume_data.get("user_id") and resume_data.get("user_id") != user_id:
        return error_response("Resume not found", 404)

    template_choice = normalize_template_choice(
        payload.get("template_choice") or resume_data.get("template_choice")
    )
    if template_choice not in VALID_TEMPLATES:
        return error_response(
            f"template_choice must be one of: {', '.join(sorted(VALID_TEMPLATES))}",
            400,
        )

    try:
        pdf_bytes = render_resume_pdf(resume_data, template_choice)
    except Exception:
        return error_response("PDF preview failed", 500)

    response = send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name="resume-preview.pdf",
        max_age=0,
    )
    response.headers["Content-Disposition"] = "inline; filename=resume-preview.pdf"
    return response


def build_resume_filename(resume, template_choice):
    name = resume.personal_info.name if resume.personal_info else ""
    parts = [name, resume.title]
    stem = "_".join(part for part in parts if part).strip("_")
    if not stem:
        stem = f"resume-{resume.id}-{template_choice}"
    stem = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")
    return stem or f"resume-{resume.id}-{template_choice}"


@resumes_bp.post("/resumes/<int:resume_id>/archive")
@rate_limit(30)
def archive_resume(resume_id):
    return set_resume_status(resume_id, "archived")


@resumes_bp.post("/resumes/<int:resume_id>/restore")
@rate_limit(30)
def restore_resume(resume_id):
    return set_resume_status(resume_id, "draft")


def set_resume_status(resume_id, status):
    payload = request.get_json(silent=True) or {}
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not resume or not user_can_access_resume(resume, get_request_user_id(payload)):
        return error_response("Resume not found", 404)

    try:
        resume.status = status
        db.session.commit()
        return success_response(serialize_resume(resume), message="Resume updated")
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


@resumes_bp.get("/templates")
def list_templates():
    return success_response(TEMPLATE_METADATA, message="Templates fetched")


@resumes_bp.get("/templates/<template_id>")
def get_template(template_id):
    template = TEMPLATE_BY_ID.get(normalize_template_choice(template_id))
    if not template:
        return error_response("Template not found", 404)
    return success_response(template, message="Template fetched")


@resumes_bp.post("/import-resume/analyze")
@resumes_bp.post("/resumes/import/analyze")
@rate_limit(12)
def analyze_imported_resume():
    try:
        extracted = validate_import_file(request.files.get("file"))
        result = analyze_resume_text(
            extracted["text"],
            filename=extracted["fileName"],
            job_description=request.form.get("job_description", ""),
            target_role=request.form.get("target_role", ""),
        )
        result["file"] = {
            "name": extracted["fileName"],
            "type": extracted["fileType"],
            "size": extracted["fileSize"],
            "pageCount": extracted["pageCount"],
        }
        result["extractedText"] = extracted["text"]
        result["extractionWarnings"] = extracted["warnings"]
        return success_response(result, message="Resume analyzed")
    except ImportValidationError as exc:
        return error_response(str(exc), exc.status_code)


@resumes_bp.post("/resumes/<int:resume_id>/ats")
@rate_limit(20)
def analyze_saved_resume(resume_id):
    payload = request.get_json(silent=True) or {}
    try:
        resume = get_resume_or_404(resume_id)
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    if not resume or not user_can_access_resume(resume, get_request_user_id(payload)):
        return error_response("Resume not found", 404)

    try:
        job_description = clean_text(
            payload.get("job_description"), "job_description", 20000
        ) or ""
        target_role = clean_text(
            payload.get("target_role") or resume.target_role, "target_role", 255
        ) or ""
        parsed, plain_text = resume_to_ats_input(resume)
        analysis = score_resume(parsed, [], plain_text, job_description, target_role)
        final_score = analysis["score"]["normalized_score"]
        resume.ats_score = final_score
        resume.job_match_score = (
            analysis["jobMatch"]["score"] if analysis.get("jobMatch") else None
        )
        resume.last_analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.add(AtsAnalysis(
            resume_id=resume.id,
            user_id=resume.user_id,
            analysis_type=analysis["analysis_type"],
            final_score=final_score,
            scoring_version=analysis["metadata"]["scoring_version"],
            job_description=job_description or None,
            breakdown=analysis["breakdown"],
            matched_requirements=[
                item for item in analysis.get("requirements", [])
                if item.get("status") in {"Matched", "Partial"}
            ],
            missing_requirements=[
                item for item in analysis.get("requirements", [])
                if item.get("status") == "Missing"
            ],
            recommendations=analysis.get("recommendations", []),
        ))
        db.session.commit()
        return success_response(
            analysis,
            message="ATS analysis completed",
        )
    except ValueError as exc:
        db.session.rollback()
        return error_response(str(exc), 400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


def resume_to_ats_input(resume):
    serialized = serialize_resume(resume)
    info = serialized.get("personal_info") or {}
    links = " ".join(info.get("links") or [])
    parsed = {
        "personalInfo": {
            "fullName": info.get("name") or "",
            "email": info.get("email") or "",
            "phone": info.get("phone") or "",
            "location": info.get("location") or "",
            "linkedin": links if "linkedin" in links.lower() else "",
            "github": links if "github" in links.lower() else "",
            "portfolio": links if links and "linkedin" not in links.lower() and "github" not in links.lower() else "",
        },
        "targetRole": serialized.get("target_role") or "",
        "summary": serialized.get("summary") or "",
        "education": serialized.get("education") or [],
        "skills": serialized.get("skills") or [],
        "experience": [
            {
                **item,
                "raw_input": "\n".join(
                    [item.get("raw_input") or "", *(item.get("ai_generated_bullets") or [])]
                ).strip(),
            }
            for item in (serialized.get("experience") or [])
        ],
        "projects": serialized.get("projects") or [],
        "certifications": serialized.get("certifications") or [],
        "languages": serialized.get("languages") or [],
        "achievements": serialized.get("achievements") or [],
    }
    parts = [
        info.get("name"),
        serialized.get("target_role"),
        info.get("email"),
        info.get("phone"),
        info.get("location"),
        links,
        "Summary",
        serialized.get("summary"),
        "Skills",
        *(item.get("skill_name") for item in parsed["skills"]),
        "Experience",
        *(" ".join(filter(None, [item.get("role"), item.get("company"), item.get("raw_input")])) for item in parsed["experience"]),
        "Education",
        *(" ".join(filter(None, [item.get("degree"), item.get("field"), item.get("school")])) for item in parsed["education"]),
        "Projects",
        *(" ".join(filter(None, [item.get("title"), item.get("description")])) for item in parsed["projects"]),
        "Certifications",
        *(" ".join(filter(None, [item.get("name"), item.get("issuer")])) for item in parsed["certifications"]),
        "Achievements",
        *(" ".join(filter(None, [item.get("title"), item.get("description")])) for item in parsed["achievements"]),
    ]
    return parsed, "\n".join(str(part) for part in parts if part)


@resumes_bp.post("/import-resume/draft")
@resumes_bp.post("/resumes/import/draft")
@rate_limit(12)
def create_imported_resume_draft():
    payload = request.get_json(silent=True) or {}
    user_id = get_request_user_id(payload)
    if not user_id:
        return error_response("Missing required user context", 400)
    parsed_resume = payload.get("parsedResume")
    if not parsed_resume:
        return error_response("Missing required field: parsedResume", 400)

    try:
        resume_payload = map_import_to_resume_payload(
            parsed_resume,
            payload.get("originalFileName") or "Imported Resume",
            user_id,
        )
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id)
            db.session.add(user)
            db.session.flush()

        resume = Resume(
            user_id=user_id,
            title=resume_payload["title"],
            target_role=extract_target_role(payload) or resume_payload.get("target_role"),
            experience_level=extract_experience_level(payload),
            template_choice=resume_payload.get("template_choice") or "steady-form",
            summary=resume_payload.get("summary"),
        )
        apply_resume_payload(resume, resume_payload)
        ats_analysis = payload.get("atsAnalysis") or {}
        ats_score = normalized_analysis_score(ats_analysis)
        if ats_score is not None:
            resume.ats_score = ats_score
            resume.job_match_score = (
                ats_analysis.get("jobMatch", {}).get("score")
                if isinstance(ats_analysis.get("jobMatch"), dict)
                else None
            )
            resume.last_analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.add(resume)
        db.session.commit()
        return success_response(
            serialize_resume(resume),
            message="Imported resume draft created",
            status_code=201,
        )
    except ValueError as exc:
        db.session.rollback()
        return error_response(str(exc), 400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return database_error_response(exc)


def normalized_analysis_score(analysis):
    if not isinstance(analysis, dict):
        return None
    score = analysis.get("score")
    if isinstance(score, dict):
        score = score.get("normalized_score")
    try:
        number = round(float(score))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, number))
