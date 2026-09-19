"""Read-only serving routes for managed media files."""

from flask import Blueprint, send_from_directory

from settings import AUDIO_UPLOAD_DIR, AVATAR_UPLOAD_DIR


uploads_bp = Blueprint("uploads", __name__)


@uploads_bp.route("/uploads/avatars/<filename>", methods=["GET"])
def serve_profile_avatar(filename):
    return send_from_directory(
        AVATAR_UPLOAD_DIR,
        filename,
        mimetype="image/webp",
        max_age=31536000,
        conditional=True,
    )


@uploads_bp.route("/uploads/audio/<filename>", methods=["GET"])
def serve_answer_audio(filename):
    return send_from_directory(
        AUDIO_UPLOAD_DIR,
        filename,
        max_age=31536000,
        conditional=True,
    )

