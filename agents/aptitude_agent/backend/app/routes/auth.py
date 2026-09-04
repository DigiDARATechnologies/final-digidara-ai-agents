from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..services.audit_service import record_event
from ..services.auth_service import authenticate, issue_token, register_student
from ..utils.authentication import require_student
from ..utils.errors import APIError
from .student import public_student

bp=Blueprint("auth",__name__,url_prefix="/api/aptitude/auth")

@bp.post("/register")
def register():
    body=request.get_json(silent=True)
    if not isinstance(body,dict):raise APIError("A JSON request body is required",400,"invalid_request")
    allowed={"name","email","password","phone","course","department","year","institution","batch"}
    if not set(body).issubset(allowed):raise APIError("Registration contains unsupported fields",400,"invalid_registration_fields")
    try:
        student=register_student(body);record_event("account_registered",student.id);db.session.commit()
    except IntegrityError as exc:
        db.session.rollback();raise APIError("An account with this email already exists",409,"email_exists") from exc
    token,expires_at=issue_token(student)
    return {"token":token,"expires_at":expires_at,"user":public_student(student)},201

@bp.post("/login")
def login():
    body=request.get_json(silent=True) or {};student=authenticate(body.get("email"),body.get("password"))
    record_event("account_login",student.id);db.session.commit();token,expires_at=issue_token(student)
    return {"token":token,"expires_at":expires_at,"user":public_student(student)}

@bp.post("/logout")
@require_student
def logout():
    g.student.token_version+=1;record_event("account_logout",g.student.id);db.session.commit()
    return {"message":"Logged out successfully"}
