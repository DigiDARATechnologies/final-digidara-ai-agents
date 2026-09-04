from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import User

profile_bp = Blueprint("profile", __name__)
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png"}
ALLOWED_PHOTO_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


@profile_bp.get("")
@jwt_required()
def get_profile():
    user = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify(user.to_dict())


@profile_bp.put("")
@jwt_required()
def update_profile():
    user = User.query.get_or_404(int(get_jwt_identity()))
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    course_name = (data.get("course_name") or "").strip()

    if len(phone) > 30:
        return jsonify({"message": "Phone number must be 30 characters or fewer"}), 400
    if len(course_name) > 120:
        return jsonify({"message": "Course name must be 120 characters or fewer"}), 400
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        return jsonify({"message": "Please enter a valid email address."}), 400
    if email and email != user.email:
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            return jsonify({"message": "That email is already in use."}), 400

    if name:
        user.name = name
    if email and email != user.email:
        user.email = email
        user.email_verified = False
    user.phone = phone or None
    user.course_name = course_name or None

    new_password = data.get("new_password")
    if new_password:
        current_password = data.get("current_password") or ""
        if not user.check_password(current_password):
            return jsonify({"message": "Current password is incorrect"}), 400
        user.set_password(new_password)

    db.session.commit()
    return jsonify(user.to_dict())


@profile_bp.post("/photo")
@jwt_required()
def upload_profile_photo():
    user = User.query.get_or_404(int(get_jwt_identity()))
    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"message": "No photo provided"}), 400

    original_name = secure_filename(file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_PHOTO_EXTENSIONS or file.mimetype not in ALLOWED_PHOTO_MIME_TYPES:
        return jsonify({"message": "Only JPG and PNG photos are supported"}), 400

    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_PHOTO_BYTES:
        return jsonify({"message": "Photo must be 5 MB or smaller"}), 400

    upload_dir = Path(current_app.config["PROFILE_UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"profile-{user.id}-{uuid4().hex}.{extension}"
    file.save(upload_dir / filename)

    old_photo_url = user.photo_url
    user.photo_url = f"/api/profile/photos/{filename}"
    db.session.commit()
    if old_photo_url:
        old_file = upload_dir / Path(old_photo_url).name
        if old_file != upload_dir / filename and old_file.exists():
            old_file.unlink()
    return jsonify(user.to_dict())


@profile_bp.get("/photos/<path:filename>")
def serve_profile_photo(filename):
    return send_from_directory(current_app.config["PROFILE_UPLOAD_FOLDER"], filename)
