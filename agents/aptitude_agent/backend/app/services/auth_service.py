from datetime import datetime, timedelta, timezone
import re
import uuid
import jwt
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash
from ..extensions import db
from ..models import Student
from ..utils.errors import APIError

EMAIL_PATTERN=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN=re.compile(r"^\+?[0-9][0-9\s-]{7,19}$")
PROFILE_LIMITS={"name":160,"email":255,"phone":24,"course":160,"department":160,"year":40,"institution":200,"batch":80}


def normalized_email(value):
    email=str(value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email) or len(email)>PROFILE_LIMITS["email"]:
        raise APIError("Enter a valid email address",400,"invalid_email")
    return email


def validated_profile(body, include_password=False):
    values={field:str(body.get(field) or "").strip() for field in PROFILE_LIMITS}
    values["email"]=normalized_email(values["email"])
    if not values["name"]:raise APIError("Student name is required",400,"name_required")
    for field,maximum in PROFILE_LIMITS.items():
        if len(values[field])>maximum:raise APIError(f"{field.replace('_',' ').title()} is too long",400,f"{field}_too_long")
    if values["phone"] and not PHONE_PATTERN.fullmatch(values["phone"]):raise APIError("Enter a valid phone number",400,"invalid_phone")
    if include_password:
        password=str(body.get("password") or "")
        if len(password)<8 or len(password)>128:raise APIError("Password must contain 8 to 128 characters",400,"invalid_password")
        values["password"]=password
    return values


def register_student(body):
    values=validated_profile(body,include_password=True)
    if Student.query.filter_by(email=values["email"]).first():raise APIError("An account with this email already exists",409,"email_exists")
    student=Student(id=str(uuid.uuid4()),name=values["name"],email=values["email"],phone=values["phone"] or None,course=values["course"] or None,department=values["department"] or None,year=values["year"] or None,institution=values["institution"] or None,batch=values["batch"] or None,password_hash=generate_password_hash(values["password"]),token_version=0)
    db.session.add(student);db.session.flush()
    return student


def authenticate(email,password):
    try:email=normalized_email(email)
    except APIError:raise APIError("Invalid email or password",401,"invalid_credentials")
    student=Student.query.filter_by(email=email).first()
    if not student or not student.password_hash or not check_password_hash(student.password_hash,str(password or "")):
        raise APIError("Invalid email or password",401,"invalid_credentials")
    return student


def issue_token(student, auth_source=None):
    now=datetime.now(timezone.utc);expires=now+timedelta(seconds=current_app.config["AUTH_TOKEN_TTL_SECONDS"])
    claims={"sub":student.id,"iat":now,"exp":expires,"aud":current_app.config["JWT_AUDIENCE"],"iss":current_app.config["JWT_ISSUER"],"ver":student.token_version}
    if auth_source:
        claims["auth_source"]=str(auth_source)
    token=jwt.encode(claims,current_app.config["JWT_SECRET"],algorithm=current_app.config["JWT_ALGORITHM"])
    return token,int(expires.timestamp())
