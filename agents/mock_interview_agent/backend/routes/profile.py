"""Student profile and avatar mutation routes."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError

import db
from services.media_storage import delete_managed_avatar
from settings import (
    ALLOWED_AVATAR_EXTENSIONS,
    ALLOWED_AVATAR_FORMATS,
    AVATAR_SIZE,
    AVATAR_UPLOAD_DIR,
    AVATAR_URL_PREFIX,
    MAX_AVATAR_PIXELS,
    MAX_AVATAR_UPLOAD_BYTES,
)
from validation import ValidationError, email as validate_email, text


profile_bp = Blueprint("profile", __name__)


def _student_profile(student_id):
    student, _ = db.query(
        """SELECT id, name, email, phone, course_enrolled, target_role, bio,
                  avatar_color, avatar_url, created_at
           FROM students
           WHERE id = %s""",
        (student_id,), fetchone=True,
    )

    if not student:
        return None

    stats, _ = db.query(
        """SELECT
             COUNT(*) AS total_interviews,
             AVG(overall_score) AS average_score,
             SUM(CASE WHEN round_type = 'technical' THEN 1 ELSE 0 END) AS technical_interviews_count,
             SUM(CASE WHEN round_type = 'hr' THEN 1 ELSE 0 END) AS hr_interviews_count
           FROM interviews
           WHERE student_id = %s AND status = 'completed'""",
        (student_id,), fetchone=True,
    )

    student.update({
        "total_interviews": int(stats["total_interviews"] or 0),
        "average_score": round(float(stats["average_score"]), 1) if stats["average_score"] is not None else None,
        "technical_interviews_count": int(stats["technical_interviews_count"] or 0),
        "hr_interviews_count": int(stats["hr_interviews_count"] or 0),
    })

    return student

@profile_bp.route("/profile/<int:student_id>", methods=["GET"])
def get_profile(student_id):
    student = _student_profile(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(student)


@profile_bp.route("/profile/<int:student_id>", methods=["PUT"])
def update_profile(student_id):
    data = request.get_json(silent=True) or {}
    validators = {
        "name": lambda value: text(
            value, "name", required=True, max_length=100
        ),
        "email": validate_email,
        "phone": lambda value: text(value, "phone", max_length=20),
        "course_enrolled": lambda value: text(
            value, "course_enrolled", max_length=150
        ),
        "target_role": lambda value: text(
            value, "target_role", max_length=100
        ),
        "bio": lambda value: text(value, "bio", max_length=5000),
        "avatar_color": lambda value: text(
            value, "avatar_color", required=True, max_length=7
        ),
    }
    updates = {
        field: validator(data[field])
        for field, validator in validators.items()
        if field in data
    }
    if "avatar_color" in updates and not (
        len(updates["avatar_color"]) == 7
        and updates["avatar_color"].startswith("#")
        and all(c in "0123456789abcdefABCDEF" for c in updates["avatar_color"][1:])
    ):
        raise ValidationError("avatar_color must be a hexadecimal color.")

    student, _ = db.query(
        "SELECT id FROM students WHERE id = %s",
        (student_id,), fetchone=True,
    )
    if not student:
        return jsonify({"error": "Student not found"}), 404

    if updates:
        set_clause = ", ".join(f"{field} = %s" for field in updates)
        params = tuple(updates.values()) + (student_id,)
        db.query(
            f"""UPDATE students
                SET {set_clause}, updated_at = NOW()
                WHERE id = %s""",
            params,
        )

    return get_profile(student_id)


@profile_bp.route("/profile/<int:student_id>/avatar", methods=["POST"])
def upload_profile_avatar(student_id):
    student, _ = db.query(
        "SELECT id, avatar_url FROM students WHERE id = %s",
        (student_id,), fetchone=True,
    )
    if not student:
        return jsonify({"error": "Student not found"}), 404

    avatar = request.files.get("avatar")
    if not avatar or not avatar.filename:
        return jsonify({"error": "Choose an image to upload."}), 400

    extension = Path(avatar.filename).suffix.lower()
    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        return jsonify({"error": "Use a JPG, JPEG, PNG, or WebP image."}), 400

    image_bytes = avatar.stream.read(MAX_AVATAR_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_AVATAR_UPLOAD_BYTES:
        max_mb = MAX_AVATAR_UPLOAD_BYTES // (1024 * 1024)
        return jsonify({"error": f"Profile photos must be {max_mb} MB or smaller."}), 413
    if not image_bytes:
        return jsonify({"error": "The selected image is empty."}), 400

    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{student_id}-{uuid4().hex}.webp"
    destination = AVATAR_UPLOAD_DIR / filename

    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in ALLOWED_AVATAR_FORMATS:
                raise ValueError("Unsupported image format")
            if source.width * source.height > MAX_AVATAR_PIXELS:
                return jsonify({"error": "The image dimensions are too large."}), 400

            source.seek(0)
            normalized = ImageOps.exif_transpose(source).convert("RGBA")
            normalized = ImageOps.fit(
                normalized,
                AVATAR_SIZE,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            normalized.save(destination, format="WEBP", quality=88, method=6)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        destination.unlink(missing_ok=True)
        return jsonify({"error": "The uploaded file is not a valid supported image."}), 400

    avatar_url = f"{AVATAR_URL_PREFIX}{filename}"
    try:
        db.query(
            """UPDATE students
               SET avatar_url = %s, updated_at = NOW()
               WHERE id = %s""",
            (avatar_url, student_id),
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    delete_managed_avatar(student.get("avatar_url"))
    return get_profile(student_id)


@profile_bp.route("/profile/<int:student_id>/avatar", methods=["DELETE"])
def remove_profile_avatar(student_id):
    student, _ = db.query(
        "SELECT id, avatar_url FROM students WHERE id = %s",
        (student_id,), fetchone=True,
    )
    if not student:
        return jsonify({"error": "Student not found"}), 404

    db.query(
        """UPDATE students
           SET avatar_url = NULL, updated_at = NOW()
           WHERE id = %s""",
        (student_id,),
    )
    delete_managed_avatar(student.get("avatar_url"))
    return get_profile(student_id)
