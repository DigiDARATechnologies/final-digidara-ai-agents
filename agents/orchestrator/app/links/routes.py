"""Opening the links Boss makes: a shared chat, and a certificate download.
Both need a signed-in, verified account; who may open each is decided in
links/service.py."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.links import service
from app.rate_limit import limiter

router = APIRouter(tags=["links"])


class ChatLinkRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=128)
    mode: str = Field(pattern="^(private|public)$")


@router.post("/links/chat")
@limiter.limit("20/minute")
def create_chat_link(req: ChatLinkRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    try:
        return service.create_chat_link(user_id, req.chat_id, req.mode)
    except service.LinkError as exc:
        raise HTTPException(exc.status, exc.message) from exc


@router.get("/links/chat/{token}")
@limiter.limit("30/minute")
def open_chat_link(token: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    try:
        return service.read_shared_chat(token, user_id)
    except service.LinkError as exc:
        raise HTTPException(exc.status, exc.message) from exc


@router.get("/links/certificate/{token}")
@limiter.limit("30/minute")
def check_certificate_link(token: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    """Whether this viewer can download with the link, before they try."""
    try:
        cert_id = service.certificate_link_owner(token, user_id)
    except service.LinkError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return {"cert_id": cert_id, "can_download": True}


@router.post("/links/certificate/{token}/download")
@limiter.limit("10/minute")
async def download_certificate(token: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> Response:
    try:
        cert_id = service.certificate_link_owner(token, user_id)
        user = auth_service.get_by_id(user_id)
        if user is None:
            raise service.LinkError(401, "Please sign in again.")
        pdf, filename = await run_in_threadpool(service.download_certificate, user, cert_id)
    except service.LinkError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })
