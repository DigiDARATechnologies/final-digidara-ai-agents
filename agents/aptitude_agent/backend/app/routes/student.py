"""Authenticated learner profile read and update endpoints."""

from io import BytesIO
import hashlib
from flask import Blueprint, g, request, send_file
from ..extensions import db
from ..models import Student
from ..services.audit_service import record_event
from ..services.auth_service import validated_profile
from ..utils.authentication import require_student
from ..utils.errors import APIError

bp=Blueprint("student",__name__,url_prefix="/api/aptitude")
PHOTO_TYPES={"image/jpeg":(b"\xff\xd8\xff",),"image/png":(b"\x89PNG\r\n\x1a\n",),"image/webp":(b"RIFF",)}
MAX_PHOTO_BYTES=2*1024*1024

def public_student(student):
    photo_version=hashlib.sha256(student.profile_photo).hexdigest()[:12] if student.profile_photo else None
    return {"id":student.id,"name":student.name,"phone":student.phone,"email":student.email,"course":student.course,"department":student.department,"year":student.year,"institution":student.institution,"batch":student.batch,"photo_url":f"/api/aptitude/me/photo?v={photo_version}" if photo_version else None}

@bp.get("/me")
@require_student
def me():
    return public_student(g.student)

@bp.patch("/me")
@require_student
def update_me():
    body=request.get_json(silent=True) or {}
    allowed={"name","phone","email","course","department","year","institution","batch"}
    if not isinstance(body,dict) or not set(body).issubset(allowed):raise APIError("Profile contains unsupported fields",400,"invalid_profile_fields")
    merged={field:body.get(field,getattr(g.student,field)) for field in allowed}
    values=validated_profile(merged)
    existing=Student.query.filter(Student.email==values["email"],Student.id!=g.student.id).first()
    if existing:raise APIError("An account with this email already exists",409,"email_exists")
    for field,value in values.items():setattr(g.student,field,value or None)
    record_event("profile_updated",g.student.id,metadata={"fields":sorted(allowed)})
    db.session.commit()
    return public_student(g.student)

@bp.get("/me/photo")
@require_student
def profile_photo():
    if not g.student.profile_photo:raise APIError("Profile photo not found",404,"photo_not_found")
    return send_file(BytesIO(g.student.profile_photo),mimetype=g.student.profile_photo_mime,download_name="profile-photo",max_age=0)

@bp.put("/me/photo")
@bp.post("/me/photo")
@require_student
def upload_profile_photo():
    photo=request.files.get("photo")
    if not photo:raise APIError("Choose an image to upload",400,"photo_required")
    if photo.mimetype not in PHOTO_TYPES:raise APIError("Use a JPEG, PNG or WebP image",400,"invalid_photo_type")
    data=photo.stream.read(MAX_PHOTO_BYTES+1)
    if len(data)>MAX_PHOTO_BYTES:raise APIError("Profile photo must be 2 MB or smaller",413,"photo_too_large")
    signatures=PHOTO_TYPES[photo.mimetype]
    valid=any(data.startswith(signature) for signature in signatures)
    if photo.mimetype=="image/webp":valid=valid and len(data)>=12 and data[8:12]==b"WEBP"
    if not valid:raise APIError("The uploaded file is not a valid image",400,"invalid_photo_content")
    g.student.profile_photo=data;g.student.profile_photo_mime=photo.mimetype
    record_event("profile_photo_updated",g.student.id);db.session.commit()
    return public_student(g.student)

@bp.delete("/me/photo")
@require_student
def delete_profile_photo():
    g.student.profile_photo=None;g.student.profile_photo_mime=None
    record_event("profile_photo_removed",g.student.id);db.session.commit()
    return public_student(g.student)
