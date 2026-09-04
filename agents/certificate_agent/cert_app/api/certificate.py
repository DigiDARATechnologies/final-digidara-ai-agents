from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os

from cert_app.schemas.exam import (
    CertificateEmailRequest,
    CertificateEmailVerificationConfirm,
    CertificateIntentRequest,
    CertificateRecipientUpdate,
)
from cert_app.services.certificate_concierge import interpret_certificate_request
from cert_app.services.exam_service import (
    get_user_certificates,
    regenerate_certificate_with_recipient_name,
    request_certificate_email_verification,
    verify_certificate_email_and_deliver,
)
from cert_app.services.auth_service import verify_token
from cert_app.db.database import get_connection

router = APIRouter()
security = HTTPBearer(auto_error=False)

    
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None)
):
    actual_token = None
    if credentials:
        actual_token = credentials.credentials
    elif token:
        actual_token = token

    if not actual_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_token(actual_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@router.get("/my-certificates")
def my_certificates(user=Depends(get_current_user)):
    certs = get_user_certificates(int(user["sub"]))
    for c in certs:
        for k, v in c.items():
            if hasattr(v, 'isoformat'):
                c[k] = str(v)
    return certs


@router.post("/interpret")
def interpret_request(request: CertificateIntentRequest, user=Depends(get_current_user)):
    """Understand a learner's natural-language certificate request."""
    return interpret_certificate_request(request.message, request.context)


@router.post("/{cert_id}/recipient")
def update_recipient_name(
    cert_id: int,
    request: CertificateRecipientUpdate,
    user=Depends(get_current_user),
):
    try:
        return regenerate_certificate_with_recipient_name(
            int(user["sub"]), cert_id, request.recipient_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{cert_id}/email")
def request_certificate_email_verification_code(
    cert_id: int,
    request: CertificateEmailRequest,
    user=Depends(get_current_user),
):
    try:
        return request_certificate_email_verification(int(user["sub"]), cert_id, request.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{cert_id}/email/verify")
def verify_certificate_email(
    cert_id: int,
    request: CertificateEmailVerificationConfirm,
    user=Depends(get_current_user),
):
    try:
        return verify_certificate_email_and_deliver(
            int(user["sub"]), cert_id, request.email, request.code
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/download/{cert_id}")
def download(cert_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM certificates WHERE id=%s AND user_id=%s",
            (cert_id, int(user["sub"]))
        )
        cert = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if not cert.get("file_path") or not os.path.exists(cert["file_path"]):
        raise HTTPException(status_code=404, detail="Certificate file missing")

    return FileResponse(
        cert["file_path"],
        media_type="application/pdf",
        filename=f"certificate_{cert['certificate_number']}.pdf"
    )
