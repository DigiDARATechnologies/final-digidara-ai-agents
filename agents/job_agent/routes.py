import json
import logging
import os
import shutil
import uuid
from datetime import date, datetime

import mysql.connector
from urllib.parse import urlparse
from flask import Blueprint, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .auth import admin_required, user_required
from .automation import get_automation_settings, set_automation_enabled
from .categories import OTHER_CATEGORY, OTHER_LABEL, load_categories, related_category_ids
from .config import ALLOWED_RESUME_EXTENSIONS, FREE_TIER_DAILY_FEED_LIMIT, PLAN_TIERS, RESUME_MAX_BYTES, UPLOAD_DIR
from .db import get_db
from .matching import parse_list, score_job
from .providers.adzuna import is_configured as is_adzuna_configured
from .providers.apify import get_apify_status
from .providers.config_loader import (
    get_adzuna_config,
    get_apify_config,
    get_greenhouse_companies,
    get_jsearch_config,
    get_pending_validation_companies,
)
from .providers.jsearch import is_configured as is_jsearch_configured
from .providers.sync import (
    queue_adzuna_collection,
    queue_apify_collection,
    queue_greenhouse_collection,
    queue_jsearch_collection,
    revalidate_greenhouse_source,
    sync_greenhouse_sources,
)
from .scraper import _validate_public_url, ScraperError
from .service import _clean_job, queue_source_run_once
from .tn_location import ALL_TN_DISTRICTS
from .chat_service import chat_with_job_agent
from .trust import evaluate_job_trust
from .usage import (
    check_and_record_chat_usage,
    check_and_record_feed_usage,
    get_token_settings,
    update_token_settings,
)


logger = logging.getLogger(__name__)

job_bp = Blueprint("job_agent", __name__)
SOURCE_TYPES = {"json_ld", "html_cards", "rss", "greenhouse", "apify", "adzuna", "jsearch"}
JOB_STATUSES = {"pending", "active", "rejected", "expired"}
APPLICATION_STATUSES = {"applied", "screening", "interview", "offer", "rejected", "withdrawn"}


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize(row):
    if not row:
        return row
    return {key: _json_value(value) for key, value in row.items()}


def _close(cursor, db):
    cursor.close()
    db.close()


def _get_profile(cursor, user_id):
    cursor.execute("SELECT * FROM user_job_profiles WHERE user_id=%s", (user_id,))
    return cursor.fetchone()


def _user_upload_dir(user_id):
    """The per-user resume folder, or None if `user_id` could somehow escape
    UPLOAD_DIR (defensive — user_id is a platform-issued id, never raw
    client input, but this is cheap insurance for a path used in deletes)."""
    upload_root = UPLOAD_DIR.resolve()
    candidate = (UPLOAD_DIR / user_id).resolve()
    if candidate != upload_root and upload_root in candidate.parents:
        return candidate
    return None


def _delete_resume_file(resume_filename):
    """Best-effort delete of one stored resume, given the DB's
    `<user_id>/<stored_name>` value. Never raises — a missing file or a
    race with a concurrent delete must not fail the caller's request."""
    if not resume_filename:
        return
    upload_root = UPLOAD_DIR.resolve()
    resume_path = (UPLOAD_DIR / resume_filename).resolve()
    if upload_root != resume_path.parent and upload_root not in resume_path.parents:
        return
    try:
        resume_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete resume file %s", resume_path, exc_info=True)


def _bounded_int(raw_value, default, minimum=0, maximum=None):
    """Parse an optional query-string int, clamped to [minimum, maximum].
    Used for admin list pagination — an invalid or missing value silently
    falls back to `default` rather than erroring, since these are optional
    refinements on an otherwise-working list endpoint."""
    try:
        value = int(raw_value) if raw_value not in (None, "") else default
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _validate_resume_magic_bytes(stream, extension: str) -> bool:
    """Verify that the uploaded stream's initial bytes match the declared extension."""
    pos = stream.tell()
    try:
        header = stream.read(32)
    finally:
        stream.seek(pos)

    if not header:
        return False
    if extension == ".pdf":
        return header.startswith(b"%PDF")
    if extension == ".docx":
        return header.startswith(b"PK\x03\x04")
    if extension == ".doc":
        return header.startswith(b"\xd0\xcf\x11\xe0")
    return False



# ---------------------------------------------------------------------------
# User-facing routes — reached only via the gateway (POST /api/invoke) by a
# logged-in DigiDARA user; g.job_user_id is the platform's own user id,
# bridged in by invoke.py's `ensure_profile` before any of these can be
# called (see db.py: user_job_actions has a real FK onto user_job_profiles).
# ---------------------------------------------------------------------------


@job_bp.route("/api/jobs/me/profile", methods=["GET", "PUT"])
@user_required
def my_profile():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if request.method == "GET":
            profile = _get_profile(cursor, g.job_user_id)
            if not profile:
                return jsonify({"error": "Profile not found"}), 404
            for field in ("skills", "preferred_titles", "preferred_locations"):
                profile[field] = parse_list(profile.get(field))
            return jsonify({"profile": _serialize(profile)})

        data = request.get_json(silent=True) or {}
        full_name = str(data.get("full_name") or "").strip()[:255]
        skills = parse_list(data.get("skills"))[:50]
        titles = parse_list(data.get("preferred_titles"))[:20]
        locations = parse_list(data.get("preferred_locations"))[:20]
        work_mode = str(data.get("preferred_work_mode") or "").strip().lower()
        if work_mode not in {"", "remote", "hybrid", "onsite"}:
            return jsonify({"error": "Invalid preferred work mode"}), 400
        try:
            experience = max(0, min(50, float(data.get("experience_years") or 0)))
        except (TypeError, ValueError):
            return jsonify({"error": "Experience must be a number"}), 400
        resume_url = str(data.get("resume_url") or "").strip()[:2000]
        if resume_url:
            parsed_resume_url = urlparse(resume_url)
            if parsed_resume_url.scheme not in {"http", "https"} or not parsed_resume_url.netloc:
                return jsonify({"error": "Invalid resume URL. Only http and https URLs are allowed."}), 400
        completed = bool(full_name and skills and titles)
        cursor.execute(
            """INSERT INTO user_job_profiles (
                user_id, full_name, skills, preferred_titles, preferred_locations,
                preferred_work_mode, experience_years, resume_url, profile_completed
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE full_name=IF(VALUES(full_name)<>'', VALUES(full_name), full_name),
                skills=VALUES(skills), preferred_titles=VALUES(preferred_titles),
                preferred_locations=VALUES(preferred_locations), preferred_work_mode=VALUES(preferred_work_mode),
                experience_years=VALUES(experience_years), resume_url=VALUES(resume_url),
                profile_completed=VALUES(profile_completed)""",
            (
                g.job_user_id, full_name, json.dumps(skills), json.dumps(titles), json.dumps(locations),
                work_mode, experience, resume_url, int(completed),
            ),
        )
        db.commit()
        return jsonify({"message": "Career profile saved", "profile_completed": completed})
    finally:
        _close(cursor, db)


@job_bp.post("/api/jobs/me/resume")
@user_required
def my_resume_upload():
    """Stores an uploaded resume file after validating extension, size, and magic bytes."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "A resume file is required"}), 400

    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in ALLOWED_RESUME_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_RESUME_EXTENSIONS))}"}), 400

    if not _validate_resume_magic_bytes(file.stream, extension):
        return jsonify({"error": "File content does not match the declared file extension"}), 400

    # Read-and-check rather than trusting Content-Length, which a client can
    # misreport; werkzeug already buffers the upload to a temp file, so this
    # costs nothing extra.
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > RESUME_MAX_BYTES:
        return jsonify({"error": f"File too large. Maximum size is {RESUME_MAX_BYTES // (1024 * 1024)}MB"}), 400

    user_dir = UPLOAD_DIR / g.job_user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    file.save(user_dir / stored_name)

    original_name = secure_filename(file.filename) or "resume"
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT IGNORE INTO user_job_profiles (user_id) VALUES (%s)", (g.job_user_id,))
        # Read the outgoing filename in the same transaction as the
        # overwrite, so a replaced resume is never left orphaned on disk —
        # without this, every re-upload leaked the previous file, which also
        # meant GDPR erasure (my_data's DELETE branch) could silently miss
        # older files it never knew about.
        cursor.execute("SELECT resume_filename FROM user_job_profiles WHERE user_id=%s", (g.job_user_id,))
        previous = cursor.fetchone()
        previous_resume_filename = previous[0] if previous else None
        cursor.execute(
            "UPDATE user_job_profiles SET resume_filename=%s, resume_original_name=%s WHERE user_id=%s",
            (f"{g.job_user_id}/{stored_name}", original_name, g.job_user_id),
        )
        db.commit()
    finally:
        cursor.close()
        db.close()
    if previous_resume_filename:
        _delete_resume_file(previous_resume_filename)
    return jsonify({"message": "Resume uploaded", "filename": original_name})


@job_bp.get("/api/jobs/me/resume")
@user_required
def my_resume_download():
    """Download the authenticated user's uploaded resume file."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        profile = _get_profile(cursor, g.job_user_id)
        if not profile or not profile.get("resume_filename"):
            return jsonify({"error": "No resume on file"}), 404
        resume_filename = profile["resume_filename"]
        original_name = profile.get("resume_original_name") or "resume"
    finally:
        _close(cursor, db)

    upload_root = UPLOAD_DIR.resolve()
    resume_path = (UPLOAD_DIR / resume_filename).resolve()
    if upload_root != resume_path.parent and upload_root not in resume_path.parents:
        return jsonify({"error": "Invalid resume path"}), 400
    if not resume_path.is_file():
        return jsonify({"error": "Resume file not found on disk"}), 404

    extension = resume_path.suffix.lower()
    mimetypes = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    mimetype = mimetypes.get(extension, "application/octet-stream")

    return send_file(
        resume_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=original_name,
    )


@job_bp.post("/api/jobs/me/chat")
@user_required
def my_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    history = data.get("history") or []
    selected_job_id = data.get("selected_job_id")
    if not message:
        return jsonify({"error": "Message is required"}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        user_balance = getattr(g, "job_token_balance", None)
        usage_res = check_and_record_chat_usage(cursor, g.job_user_id, user_token_balance=user_balance)
        if usage_res.get("insufficient_tokens"):
            return jsonify({
                "error": "insufficient_tokens",
                "message": f"Daily free chat quota of {usage_res['free_daily_turns']} messages reached. Please top up tokens to continue chatting.",
                "required_tokens": usage_res["required_tokens"],
                "current_balance": usage_res.get("current_balance", 0),
                "free_daily_turns": usage_res["free_daily_turns"],
                "prompt_topup": True,
            }), 402
        db.commit()
    finally:
        _close(cursor, db)

    res = chat_with_job_agent(
        g.job_user_id,
        message,
        history,
        selected_job_id=selected_job_id,
    )
    res["daily_usage"] = {
        "free_turns_remaining": usage_res["free_turns_remaining"],
        "total_turns_today": usage_res["total_turns_today"],
        "tokens_charged": usage_res["tokens_charged"],
    }
    resp = jsonify(res)
    resp.headers["X-Tokens-Used"] = str(usage_res["tokens_charged"])
    return resp


@job_bp.get("/api/jobs/me/categories")
@user_required
def my_categories():
    categories = [{"id": category["id"], "label": category["label"]} for category in load_categories()]
    categories.append({"id": OTHER_CATEGORY, "label": OTHER_LABEL})
    return jsonify({"categories": categories})


@job_bp.get("/api/jobs/me/feed")
@user_required
def my_feed():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        profile = _get_profile(cursor, g.job_user_id) or {}
        plan_tier = profile.get("plan_tier") or "free"

        query = (request.args.get("q") or "").strip()
        mode = (request.args.get("work_mode") or "").strip().lower()
        category = (request.args.get("category") or "").strip()
        saved_only = (request.args.get("saved") or "").strip().lower() in {"1", "true", "yes"}
        params = [g.job_user_id]
        where = ["j.status='active'", "(j.expires_at IS NULL OR j.expires_at >= NOW())", "COALESCE(a.is_hidden,0)=0"]
        if saved_only:
            where.append("COALESCE(a.is_saved,0)=1")
        if query:
            where.append("(j.title LIKE %s OR j.company LIKE %s OR j.description LIKE %s)")
            pattern = f"%{query}%"
            params.extend([pattern, pattern, pattern])
        if mode in {"remote", "hybrid", "onsite"}:
            where.append("j.work_mode=%s")
            params.append(mode)
        if category and category != "all":
            valid_category_ids = {c["id"] for c in load_categories()} | {OTHER_CATEGORY}
            if category in valid_category_ids:
                # Broader relevant results, not a narrow filter: a category
                # also pulls in jobs from its related categories.
                category_ids = {category} | related_category_ids(category)
                placeholders = ",".join(["%s"] * len(category_ids))
                where.append(f"j.category IN ({placeholders})")
                params.extend(category_ids)
        cursor.execute(
            f"""SELECT j.*, COALESCE(a.is_saved,0) AS is_saved, a.application_status
                FROM jobs j
                LEFT JOIN user_job_actions a ON a.job_id=j.id AND a.user_id=%s
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(j.published_at,j.created_at) DESC LIMIT 500""",
            tuple(params),
        )
        # No certified-course concept in this standalone agent (see
        # matching.py's `score_job` third argument, originally the
        # certification portal's course name) — the user's own preferred
        # titles stand in for it, so category-relatedness scoring still has
        # a real signal to work from instead of always degrading to zero.
        preferred_titles_text = " ".join(parse_list(profile.get("preferred_titles")))
        jobs = cursor.fetchall()
        for job in jobs:
            job["skills"] = parse_list(job.get("skills"))
            score, reasons = score_job(job, profile, preferred_titles_text)
            job["match_score"] = score
            job["match_reasons"] = reasons
            job.update(evaluate_job_trust(job))

        def _feed_sort_key(item):
            dt = item.get("published_at") or item.get("created_at")
            if isinstance(dt, (datetime, date)):
                dt_key = dt.isoformat()
            else:
                dt_key = str(dt or "")
            is_entry = 1 if item.get("seniority_tier") == "entry" else 0
            return (is_entry, item["match_score"], dt_key)

        jobs.sort(key=_feed_sort_key, reverse=True)


        # Dynamic SaaS Feed Quota & Token Gating
        user_balance = getattr(g, "job_token_balance", None)
        requested_count = 20

        if plan_tier != "free":
            # Paid plan tier bypasses daily feed limits
            limit = 200
            capped = jobs[:limit]
            resp = jsonify({
                "jobs": [_serialize(job) for job in capped],
                "total": len(jobs),
                "returned": len(capped),
                "plan_tier": plan_tier,
                "limit": limit,
            })
            resp.headers["X-Tokens-Used"] = "0"
            return resp

        usage_res = check_and_record_feed_usage(
            cursor,
            g.job_user_id,
            requested_count=requested_count,
            user_token_balance=user_balance,
        )

        if usage_res.get("insufficient_tokens"):
            return jsonify({
                "error": "insufficient_tokens",
                "message": f"You have reached your daily free limit of {usage_res['free_daily_limit']} jobs. Please top up your tokens to unlock more opportunities.",
                "required_tokens": usage_res["required_tokens"],
                "current_balance": usage_res.get("current_balance", 0),
                "free_daily_limit": usage_res["free_daily_limit"],
                "prompt_topup": True,
            }), 402

        db.commit()

        limit = usage_res["jobs_served"] if usage_res["jobs_served"] > 0 else requested_count
        capped = jobs[:limit]
        resp = jsonify({
            "jobs": [_serialize(job) for job in capped],
            "total": len(jobs),
            "returned": len(capped),
            "plan_tier": plan_tier,
            "limit": limit,
            "daily_usage": {
                "free_quota_remaining": usage_res["free_quota_remaining"],
                "total_viewed_today": usage_res["total_viewed_today"],
                "free_daily_limit": usage_res["free_daily_limit"],
                "tokens_charged": usage_res["tokens_charged"],
            },
        })
        resp.headers["X-Tokens-Used"] = str(usage_res["tokens_charged"])
        return resp
    finally:
        _close(cursor, db)


@job_bp.get("/api/jobs/me/saved")
@user_required
def my_saved_jobs():
    """All saved jobs, independent of the current profile-match feed cap."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT j.id, j.title, j.company, j.location, j.work_mode, j.apply_url,
                      j.status, j.expires_at, a.application_status, a.updated_at
               FROM user_job_actions a JOIN jobs j ON j.id=a.job_id
               WHERE a.user_id=%s AND a.is_saved=1 AND a.is_hidden=0
               ORDER BY a.updated_at DESC LIMIT 200""",
            (g.job_user_id,),
        )
        return jsonify({"jobs": [_serialize(row) for row in cursor.fetchall()]})
    finally:
        _close(cursor, db)


@job_bp.get("/api/jobs/me/hidden")
@user_required
def my_hidden_jobs():
    """Every job this user has hidden — the only way to find one again to
    call the `unhide` job_action on it, since a hidden job is excluded from
    both the matched feed and the saved-jobs list."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT j.id, j.title, j.company, j.location, j.work_mode, j.apply_url,
                      j.status, a.updated_at
               FROM user_job_actions a JOIN jobs j ON j.id=a.job_id
               WHERE a.user_id=%s AND a.is_hidden=1
               ORDER BY a.updated_at DESC LIMIT 200""",
            (g.job_user_id,),
        )
        return jsonify({"jobs": [_serialize(row) for row in cursor.fetchall()]})
    finally:
        _close(cursor, db)


@job_bp.put("/api/jobs/me/jobs/<int:job_id>/action")
@user_required
def my_job_action(job_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, status FROM jobs WHERE id=%s", (job_id,))
        job = cursor.fetchone()
        if not job or job["status"] != "active":
            return jsonify({"error": "Active job not found"}), 404

        data = request.get_json(silent=True) or {}
        action = data.get("action")
        if action not in {"save", "unsave", "hide", "unhide", "apply"}:
            return jsonify({"error": "Invalid job action"}), 400

        saved = action == "save"
        hidden = action == "hide"
        applied = action == "apply"
        cursor.execute(
            """INSERT INTO user_job_actions (
                user_id, job_id, is_saved, is_hidden, application_status, applied_at
            ) VALUES (%s,%s,%s,%s,%s,IF(%s,NOW(),NULL))
            ON DUPLICATE KEY UPDATE
                is_saved=IF(%s,1,IF(%s,0,is_saved)),
                is_hidden=IF(%s,1,IF(%s,0,is_hidden)),
                application_status=IF(%s,'applied',application_status),
                applied_at=IF(%s,COALESCE(applied_at,NOW()),applied_at)""",
            (
                g.job_user_id, job_id, int(saved), int(hidden), "applied" if applied else None, int(applied),
                int(saved), int(action == "unsave"),
                int(hidden), int(action == "unhide"),
                int(applied), int(applied),
            ),
        )
        db.commit()
        return jsonify({"message": "Job action updated", "action": action})
    finally:
        _close(cursor, db)


@job_bp.get("/api/jobs/me/applications")
@user_required
def my_applications():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT j.id, j.title, j.company, j.location, j.apply_url,
                      a.application_status, a.applied_at, a.updated_at
               FROM user_job_actions a JOIN jobs j ON j.id=a.job_id
               WHERE a.user_id=%s AND a.application_status IS NOT NULL
               ORDER BY a.applied_at DESC""",
            (g.job_user_id,),
        )
        return jsonify({"applications": [_serialize(row) for row in cursor.fetchall()]})
    finally:
        _close(cursor, db)


@job_bp.route("/api/jobs/me/data", methods=["GET", "DELETE"])
@user_required
def my_data():
    """Export or erase all Job Agent data owned by the authenticated user."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        profile = _get_profile(cursor, g.job_user_id)
        if request.method == "GET":
            if profile:
                for field in ("skills", "preferred_titles", "preferred_locations"):
                    profile[field] = parse_list(profile.get(field))
            cursor.execute(
                """SELECT a.job_id, j.title, j.company, j.apply_url,
                          a.is_saved, a.is_hidden, a.application_status,
                          a.applied_at, a.created_at, a.updated_at
                   FROM user_job_actions a
                   JOIN jobs j ON j.id=a.job_id
                   WHERE a.user_id=%s ORDER BY a.created_at""",
                (g.job_user_id,),
            )
            return jsonify({
                "profile": _serialize(profile) if profile else None,
                "job_actions": [_serialize(row) for row in cursor.fetchall()],
            })

        cursor.execute("DELETE FROM user_job_profiles WHERE user_id=%s", (g.job_user_id,))
        db.commit()
    finally:
        _close(cursor, db)

    # Removes the whole per-user folder, not just the currently-tracked
    # resume_filename — re-uploading used to leak the previous file (see
    # my_resume_upload's cleanup, added alongside this), so relying on a
    # single tracked filename here could leave older resumes behind for
    # any account that had uploaded more than one. shutil.rmtree with
    # ignore_errors covers "never uploaded a resume" (no folder to remove)
    # and "already erased" the same way: nothing to do, not an error.
    user_dir = _user_upload_dir(g.job_user_id)
    if user_dir is not None:
        shutil.rmtree(user_dir, ignore_errors=True)
    return jsonify({"message": "Job Agent user data deleted"})


# ---------------------------------------------------------------------------
# Admin routes — reached only via the gateway too, but gated on the
# platform's verified `X-Digidara-Is-Admin` header (see auth.py) rather than
# a separate admin login. Ops-only: never exposed in the chat flow.
# ---------------------------------------------------------------------------


@job_bp.get("/api/jobs/admin/users")
@admin_required
def admin_users():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT user_id, plan_tier, profile_completed, experience_years,
                      preferred_work_mode, created_at, updated_at
               FROM user_job_profiles ORDER BY created_at DESC LIMIT 500"""
        )
        return jsonify({"users": [_serialize(row) for row in cursor.fetchall()]})
    finally:
        _close(cursor, db)


@job_bp.put("/api/jobs/admin/users/<user_id>/plan")
@admin_required
def admin_update_plan(user_id):
    data = request.get_json(silent=True) or {}
    plan_tier = str(data.get("plan_tier") or "").strip().lower()
    if plan_tier not in PLAN_TIERS:
        return jsonify({"error": f"plan_tier must be one of {sorted(PLAN_TIERS)}"}), 400
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE user_job_profiles SET plan_tier=%s WHERE user_id=%s", (plan_tier, user_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "User profile not found"}), 404
        db.commit()
        return jsonify({"message": "Plan updated", "plan_tier": plan_tier})
    finally:
        _close(cursor, db)


@job_bp.route("/api/jobs/admin/token-settings", methods=["GET", "PUT"])
@admin_required
def admin_token_settings():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if request.method == "GET":
            settings = get_token_settings(cursor)
            return jsonify({"token_settings": settings})

        data = request.get_json(silent=True) or {}
        new_feed = _bounded_int(data.get("free_daily_feed_limit"), default=None, minimum=1, maximum=1000) if "free_daily_feed_limit" in data else None
        new_chat = _bounded_int(data.get("free_daily_chat_turns"), default=None, minimum=1, maximum=1000) if "free_daily_chat_turns" in data else None
        new_extra_feed = _bounded_int(data.get("tokens_per_extra_feed"), default=None, minimum=0, maximum=100000) if "tokens_per_extra_feed" in data else None
        new_extra_chat = _bounded_int(data.get("tokens_per_chat_turn"), default=None, minimum=0, maximum=50000) if "tokens_per_chat_turn" in data else None

        updated = update_token_settings(
            cursor,
            free_daily_feed_limit=new_feed,
            free_daily_chat_turns=new_chat,
            tokens_per_extra_feed=new_extra_feed,
            tokens_per_chat_turn=new_extra_chat,
        )
        db.commit()
        return jsonify({"message": "Token settings updated successfully", "token_settings": updated})
    finally:
        _close(cursor, db)



@job_bp.route("/api/jobs/admin/sources", methods=["GET", "POST"])
@admin_required
def admin_sources():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if request.method == "GET":
            limit = _bounded_int(request.args.get("limit"), default=200, minimum=1, maximum=500)
            offset = _bounded_int(request.args.get("offset"), default=0, minimum=0)
            cursor.execute("SELECT COUNT(*) AS n FROM job_sources")
            total = cursor.fetchone()["n"]
            cursor.execute(
                "SELECT * FROM job_sources ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset)
            )
            return jsonify({
                "sources": [_serialize(row) for row in cursor.fetchall()], "total": total, "limit": limit, "offset": offset,
            })

        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        source_type = str(data.get("source_type") or "").strip()
        source_url = str(data.get("source_url") or "").strip()
        authorized = data.get("scraping_authorized") is True
        if not name or source_type not in SOURCE_TYPES or not source_url:
            return jsonify({"error": "Name, valid source type, and source URL are required"}), 400
        try:
            _validate_public_url(source_url)
            parser_config = data.get("parser_config") or {}
            if isinstance(parser_config, str):
                parser_config = json.loads(parser_config or "{}")
        except (ScraperError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            cursor.execute(
                """INSERT INTO job_sources
                   (name, source_type, source_url, parser_config, is_active, scraping_authorized)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (name, source_type, source_url, json.dumps(parser_config), 1, int(authorized)),
            )
        except mysql.connector.IntegrityError:
            return jsonify({"error": "A job source with this name already exists"}), 409
        db.commit()
        return jsonify({"message": "Job source created", "id": cursor.lastrowid}), 201
    finally:
        _close(cursor, db)


@job_bp.route("/api/jobs/admin/automation", methods=["GET", "PUT"])
@admin_required
def admin_automation():
    if request.method == "GET":
        return jsonify({"automation": _serialize(get_automation_settings())})
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("enabled"), bool):
        return jsonify({"error": "enabled must be true or false"}), 400
    return jsonify({"automation": _serialize(set_automation_enabled(data["enabled"]))})


@job_bp.put("/api/jobs/admin/sources/<int:source_id>/status")
@admin_required
def admin_source_status(source_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("is_active"), bool):
        return jsonify({"error": "is_active must be true or false"}), 400
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE job_sources SET is_active=%s WHERE id=%s", (int(data["is_active"]), source_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Source not found"}), 404
        db.commit()
        return jsonify({"message": "Source status updated"})
    finally:
        _close(cursor, db)


@job_bp.post("/api/jobs/admin/sources/<int:source_id>/run")
@admin_required
def admin_queue_run(source_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, is_active, scraping_authorized FROM job_sources WHERE id=%s", (source_id,))
        source = cursor.fetchone()
        if not source:
            return jsonify({"error": "Source not found"}), 404
        if not source["is_active"] or not source["scraping_authorized"]:
            return jsonify({"error": "Source must be active and explicitly authorized"}), 409
    finally:
        _close(cursor, db)
    run_id, created = queue_source_run_once(source_id, g.job_user_id)
    message = "Scrape run queued" if created else "This source already has a queued or running scrape"
    return jsonify({"message": message, "run_id": run_id, "queued": created}), 202 if created else 200


@job_bp.get("/api/jobs/admin/runs")
@admin_required
def admin_runs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        limit = _bounded_int(request.args.get("limit"), default=100, minimum=1, maximum=500)
        offset = _bounded_int(request.args.get("offset"), default=0, minimum=0)
        cursor.execute("SELECT COUNT(*) AS n FROM job_ingestion_runs")
        total = cursor.fetchone()["n"]
        cursor.execute(
            """SELECT r.*, s.name AS source_name FROM job_ingestion_runs r
               JOIN job_sources s ON s.id=r.source_id ORDER BY r.queued_at DESC LIMIT %s OFFSET %s""",
            (limit, offset),
        )
        return jsonify({
            "runs": [_serialize(row) for row in cursor.fetchall()], "total": total, "limit": limit, "offset": offset,
        })
    finally:
        _close(cursor, db)


@job_bp.route("/api/jobs/admin/jobs", methods=["GET", "POST"])
@admin_required
def admin_jobs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if request.method == "GET":
            status = request.args.get("status")
            category = (request.args.get("category") or "").strip()
            location = (request.args.get("location") or "").strip()
            limit = _bounded_int(request.args.get("limit"), default=500, minimum=1, maximum=500)
            offset = _bounded_int(request.args.get("offset"), default=0, minimum=0)
            where, params = [], []
            if status in JOB_STATUSES:
                where.append("status=%s")
                params.append(status)
            if category and category != "all":
                where.append("category=%s")
                params.append(category)
            if location:
                where.append("location LIKE %s")
                params.append(f"%{location}%")
            clause = f"WHERE {' AND '.join(where)}" if where else ""
            cursor.execute(f"SELECT COUNT(*) AS n FROM jobs {clause}", tuple(params))
            total = cursor.fetchone()["n"]
            cursor.execute(
                f"SELECT * FROM jobs {clause} ORDER BY created_at DESC LIMIT %s OFFSET %s", (*params, limit, offset)
            )
            rows = cursor.fetchall()
            for row in rows:
                row["skills"] = parse_list(row.get("skills"))
            return jsonify({
                "jobs": [_serialize(row) for row in rows], "total": total, "limit": limit, "offset": offset,
            })

        data = request.get_json(silent=True) or {}
        requested_category = str(data.get("category") or "").strip()
        job = _clean_job({
            "external_id": str(data.get("external_id") or "manual-" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")),
            "title": str(data.get("title") or "").strip(),
            "company": str(data.get("company") or "").strip(),
            "location": str(data.get("location") or "").strip(),
            "work_mode": str(data.get("work_mode") or "").strip().lower(),
            "employment_type": str(data.get("employment_type") or "").strip(),
            "department": str(data.get("department") or "").strip(),
            "category": requested_category or None,
            "description": str(data.get("description") or "").strip(),
            "skills": parse_list(data.get("skills")),
            "apply_url": str(data.get("apply_url") or "").strip(),
            "source_url": str(data.get("apply_url") or "").strip(),
            "published_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if not job:
            return jsonify({"error": "Title, company, and apply URL are required"}), 400
        try:
            _validate_public_url(job["apply_url"])
        except ScraperError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            cursor.execute(
                """INSERT INTO jobs (external_id,title,company,location,work_mode,employment_type,
                   department,category,description,skills,apply_url,source_url,published_at,status,content_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s)""",
                (
                    job["external_id"], job["title"], job["company"], job.get("location"),
                    job.get("work_mode"), job.get("employment_type"), job.get("department"), job.get("category"),
                    job.get("description"), job["skills"], job["apply_url"], job.get("source_url"),
                    job.get("published_at"), job["content_hash"],
                ),
            )
        except mysql.connector.IntegrityError:
            return jsonify({"error": "This job already exists"}), 409
        db.commit()
        return jsonify({"message": "Job published", "id": cursor.lastrowid}), 201
    finally:
        _close(cursor, db)


@job_bp.put("/api/jobs/admin/jobs/<int:job_id>/status")
@admin_required
def admin_job_status(job_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in JOB_STATUSES:
        return jsonify({"error": "Invalid job status"}), 400
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE jobs SET status=%s WHERE id=%s", (status, job_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Job not found"}), 404
        db.commit()
        return jsonify({"message": "Job status updated", "status": status})
    finally:
        _close(cursor, db)


@job_bp.put("/api/jobs/admin/jobs/bulk-status")
@admin_required
def admin_jobs_bulk_status():
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    job_ids = data.get("ids")
    if status not in JOB_STATUSES:
        return jsonify({"error": "Invalid job status"}), 400
    if not isinstance(job_ids, list) or not job_ids:
        return jsonify({"error": "ids must be a non-empty list of job ids"}), 400
    try:
        job_ids = [int(job_id) for job_id in job_ids][:1000]
    except (TypeError, ValueError):
        return jsonify({"error": "ids must all be integers"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        placeholders = ",".join(["%s"] * len(job_ids))
        cursor.execute(
            f"UPDATE jobs SET status=%s WHERE id IN ({placeholders})",
            (status, *job_ids),
        )
        updated = cursor.rowcount
        db.commit()
        return jsonify({"message": f"{updated} job(s) updated", "status": status, "updated": updated})
    finally:
        _close(cursor, db)


@job_bp.post("/api/jobs/admin/jobs/prune")
@admin_required
def admin_prune_jobs():
    data = request.get_json(silent=True) or {}
    max_age_days = _bounded_int(data.get("max_age_days"), default=30, minimum=1, maximum=365)
    from .service import prune_expired_jobs
    outcome = prune_expired_jobs(max_age_days=max_age_days)
    return jsonify({
        "message": f"Successfully pruned expired jobs and records older than {max_age_days} days",
        **outcome,
    })


@job_bp.get("/api/jobs/admin/categories")
@admin_required
def admin_categories():
    categories = [{"id": category["id"], "label": category["label"]} for category in load_categories()]
    categories.append({"id": OTHER_CATEGORY, "label": OTHER_LABEL})
    return jsonify({"categories": categories})


def _greenhouse_company_rows():
    """Per-company Greenhouse rows: registry metadata + source health + job counts."""
    companies = get_greenhouse_companies()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, name, is_active, status, error_category, last_run_at,
                      last_attempted_at, last_success_at, last_validated_at,
                      last_error, consecutive_failures, last_fetched_count
               FROM job_sources WHERE source_type='greenhouse'"""
        )
        by_name = {row["name"]: row for row in cursor.fetchall()}

        cursor.execute(
            """SELECT source_id, COUNT(*) AS total_jobs,
                      SUM(CASE WHEN location_region='TAMIL_NADU' THEN 1 ELSE 0 END) AS tn_jobs,
                      SUM(CASE WHEN location_region='OTHER_INDIA' THEN 1 ELSE 0 END) AS other_india_jobs,
                      SUM(CASE WHEN location_region='INTERNATIONAL' THEN 1 ELSE 0 END) AS international_jobs,
                      SUM(CASE WHEN location_region IS NULL OR location_region='UNKNOWN' THEN 1 ELSE 0 END) AS unknown_jobs
               FROM jobs WHERE source_id IN (
                   SELECT id FROM job_sources WHERE source_type='greenhouse'
               ) GROUP BY source_id"""
        )
        job_counts_by_source_id = {row["source_id"]: row for row in cursor.fetchall()}
    finally:
        _close(cursor, db)

    result = []
    for company in companies:
        source = by_name.get(f"greenhouse:{company['board_id']}")
        counts = job_counts_by_source_id.get(source["id"]) if source else None
        result.append({
            **company,
            "source_id": source["id"] if source else None,
            "synced": source is not None,
            "is_active": bool(source["is_active"]) if source else False,
            "status": source["status"] if source else "discovered",
            "error_category": source.get("error_category") if source else None,
            "consecutive_failures": source.get("consecutive_failures", 0) if source else 0,
            "last_run_at": _json_value(source["last_run_at"]) if source else None,
            "last_attempted_at": _json_value(source["last_attempted_at"]) if source else None,
            "last_validated_at": _json_value(source["last_validated_at"]) if source else None,
            "last_success_at": _json_value(source["last_success_at"]) if source else None,
            "last_error": source.get("last_error") if source else None,
            "fetched_job_count": source.get("last_fetched_count") if source else None,
            "total_jobs": int(counts["total_jobs"]) if counts else 0,
            "tn_job_count": int(counts["tn_jobs"] or 0) if counts else 0,
            "other_india_job_count": int(counts["other_india_jobs"] or 0) if counts else 0,
            "international_job_count": int(counts["international_jobs"] or 0) if counts else 0,
            "unknown_location_job_count": int(counts["unknown_jobs"] or 0) if counts else 0,
        })
    return result


@job_bp.get("/api/jobs/admin/providers/greenhouse/companies")
@admin_required
def admin_greenhouse_companies():
    return jsonify({"companies": _greenhouse_company_rows()})


@job_bp.get("/api/jobs/admin/providers/greenhouse/summary")
@admin_required
def admin_greenhouse_summary():
    rows = _greenhouse_company_rows()
    by_status = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return jsonify({
        "company_count": len(rows),
        "companies_by_status": by_status,
        "total_jobs": sum(row["total_jobs"] for row in rows),
        "tamil_nadu": sum(row["tn_job_count"] for row in rows),
        "other_india": sum(row["other_india_job_count"] for row in rows),
        "international": sum(row["international_job_count"] for row in rows),
        "unknown": sum(row["unknown_location_job_count"] for row in rows),
    })


@job_bp.get("/api/jobs/admin/providers/greenhouse/pending-companies")
@admin_required
def admin_greenhouse_pending_companies():
    return jsonify({"companies": get_pending_validation_companies()})


@job_bp.get("/api/jobs/admin/tn-coverage")
@admin_required
def admin_tn_coverage():
    published_only = (request.args.get("published_only") or "").strip().lower() in {"1", "true", "yes"}
    status_filter = "status='active'" if published_only else "status != 'rejected'"
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            f"""SELECT location_district, COUNT(*) AS job_count
               FROM jobs WHERE location_region='TAMIL_NADU' AND {status_filter}
               GROUP BY location_district"""
        )
        counts = {row["location_district"]: row["job_count"] for row in cursor.fetchall()}

        cursor.execute(
            f"""SELECT location_region, COUNT(*) AS job_count
               FROM jobs WHERE {status_filter} GROUP BY location_region"""
        )
        by_region = {(row["location_region"] or "UNKNOWN"): row["job_count"] for row in cursor.fetchall()}
    finally:
        _close(cursor, db)

    districts = [
        {"district": district, "jobs": counts.get(district, 0)}
        for district in ALL_TN_DISTRICTS
    ]
    return jsonify({
        "districts": districts,
        "total_tamil_nadu_jobs": sum(counts.values()),
        "by_region": {
            "TAMIL_NADU": by_region.get("TAMIL_NADU", 0),
            "OTHER_INDIA": by_region.get("OTHER_INDIA", 0),
            "INTERNATIONAL": by_region.get("INTERNATIONAL", 0),
            "UNKNOWN": by_region.get("UNKNOWN", 0),
        },
    })


@job_bp.post("/api/jobs/admin/providers/greenhouse/sources/<int:source_id>/revalidate")
@admin_required
def admin_greenhouse_revalidate(source_id):
    outcome = revalidate_greenhouse_source(source_id, admin_id=g.job_user_id)
    if outcome is None:
        return jsonify({"error": "Greenhouse source not found"}), 404
    return jsonify({
        "message": "Revalidation complete" if outcome["run"]["status"] == "success" else "Revalidation failed",
        "source": _serialize(outcome["source"]),
        "run": outcome["run"],
    })


@job_bp.post("/api/jobs/admin/providers/greenhouse/sync")
@admin_required
def admin_greenhouse_sync():
    synced = sync_greenhouse_sources()
    return jsonify({"message": "Greenhouse sources synced", "companies": synced})


@job_bp.post("/api/jobs/admin/providers/greenhouse/run")
@admin_required
def admin_greenhouse_run():
    result = queue_greenhouse_collection(admin_id=g.job_user_id)
    return jsonify({"message": "Greenhouse collection queued", **result}), 202


@job_bp.get("/api/jobs/admin/providers/apify/status")
@admin_required
def admin_apify_status():
    status = get_apify_status(get_apify_config())
    return jsonify(status)


@job_bp.get("/api/jobs/admin/providers/apify/actors")
@admin_required
def admin_apify_actors():
    """One row per configured platform (Naukri, LinkedIn, ...) — actor id,
    whether it's enabled, and its job_sources health once synced at least
    once. Powers the admin panel's per-platform "Run now" buttons."""
    actors = get_apify_config()["actors"]
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, parser_config, status, last_run_at, last_error, last_fetched_count
               FROM job_sources WHERE source_type='apify'"""
        )
        by_platform = {}
        for row in cursor.fetchall():
            platform = json.loads(row.get("parser_config") or "{}").get("platform")
            if platform:
                by_platform[platform] = row
    finally:
        _close(cursor, db)

    result = []
    for actor in actors:
        source = by_platform.get(actor["platform"])
        result.append({
            "platform": actor["platform"],
            "source_id": source["id"] if source else None,
            "actor_id": actor["actor_id"],
            "configured": bool(actor["actor_id"]) and actor["enabled"],
            "status": source["status"] if source else "not_synced",
            "last_run_at": _json_value(source["last_run_at"]) if source else None,
            "last_error": source.get("last_error") if source else None,
            "last_fetched_count": source.get("last_fetched_count") if source else None,
        })
    return jsonify({"actors": result})


@job_bp.post("/api/jobs/admin/providers/apify/run")
@admin_required
def admin_apify_run():
    data = request.get_json(silent=True) or {}
    platform = str(data.get("platform") or "").strip() or None
    status = queue_apify_collection(admin_id=g.job_user_id, platform=platform)
    if not status.get("ready"):
        return jsonify(status), 409
    return jsonify({"message": "Apify collection queued", **status}), 202


@job_bp.get("/api/jobs/admin/providers/adzuna/status")
@admin_required
def admin_adzuna_status():
    config = get_adzuna_config()
    configured = is_adzuna_configured()
    return jsonify({
        "ready": configured and config["enabled"],
        "enabled": config["enabled"],
        "configured": configured,
        "queries_count": len(config["queries"]),
        "reason": "" if configured else "ADZUNA_APP_ID or ADZUNA_APP_KEY is not set",
    })


@job_bp.post("/api/jobs/admin/providers/adzuna/run")
@admin_required
def admin_adzuna_run():
    status = queue_adzuna_collection(admin_id=g.job_user_id)
    if not status.get("ready"):
        return jsonify(status), 409
    return jsonify({"message": "Adzuna collection queued", **status}), 202


@job_bp.get("/api/jobs/admin/providers/jsearch/status")
@admin_required
def admin_jsearch_status():
    config = get_jsearch_config()
    configured = is_jsearch_configured()
    return jsonify({
        "ready": configured and config["enabled"],
        "enabled": config["enabled"],
        "configured": configured,
        "queries_count": len(config["queries"]),
        "reason": "" if configured else "RAPIDAPI_KEY is not set",
    })


@job_bp.post("/api/jobs/admin/providers/jsearch/run")
@admin_required
def admin_jsearch_run():
    status = queue_jsearch_collection(admin_id=g.job_user_id)
    if not status.get("ready"):
        return jsonify(status), 409
    return jsonify({"message": "JSearch collection queued", **status}), 202

