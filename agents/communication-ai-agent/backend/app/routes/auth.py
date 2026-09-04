from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__)

GUEST_EMAIL = "guest@student.local"
GUEST_PASSWORD = "guest-student-password"


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"message": "name, email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "An account with this email already exists"}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.post("/guest")
def guest():
    try:
        user = User.query.filter_by(email=GUEST_EMAIL).first()
        if not user:
            user = User(name="Guest Student", email=GUEST_EMAIL)
            user.set_password(GUEST_PASSWORD)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                # React dev mode / fast refresh can fire guest login twice at the
                # same time. If the competing request created the shared guest
                # account first, recover by loading it instead of returning 500.
                db.session.rollback()
                user = User.query.filter_by(email=GUEST_EMAIL).first()
                if not user:
                    raise
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Guest login failed")
        return jsonify({
            "message": "Guest sign-in is unavailable. Confirm MySQL is running and the users table is up to date.",
            "error_code": "GUEST_LOGIN_FAILED",
        }), 503

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200
