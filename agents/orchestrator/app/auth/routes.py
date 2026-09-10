from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import google_oauth, service
from app.auth.schemas import ChangePasswordRequest, GoogleAuthRequest, LoginRequest, SignupRequest, TokenResponse, UserOut
from app.auth.security import create_access_token, get_current_user_id, hash_password, verify_password
from app.models import User
from app.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Neither route carries a bearer token yet, so `limiter`'s key function
# falls back to per-IP — exactly what a credential-stuffing / signup-spam
# guard on these two routes needs.
_LOGIN_RATE_LIMIT = "5/minute"


def _to_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, mobile=user.mobile, is_admin=user.is_admin)


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit(_LOGIN_RATE_LIMIT)
def signup(req: SignupRequest, request: Request) -> TokenResponse:
    email = req.email.strip().lower()
    if service.get_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = service.create_user(req.name.strip(), email, req.mobile, hash_password(req.password))
    return TokenResponse(access_token=create_access_token(user.id), user=_to_out(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_LOGIN_RATE_LIMIT)
def login(req: LoginRequest, request: Request) -> TokenResponse:
    user = service.get_by_email(req.email.strip().lower())
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return TokenResponse(access_token=create_access_token(user.id), user=_to_out(user))


@router.post("/google", response_model=TokenResponse)
def google_auth(req: GoogleAuthRequest) -> TokenResponse:
    profile = google_oauth.exchange_code(req.code, req.redirect_uri)

    user = service.get_by_google_id(profile.sub)
    if not user:
        existing = service.get_by_email(profile.email)
        user = service.link_google_id(existing.id, profile.sub) if existing else service.create_google_user(profile.name, profile.email, profile.sub)

    return TokenResponse(access_token=create_access_token(user.id), user=_to_out(user))


@router.get("/me", response_model=UserOut)
def me(user_id: str = Depends(get_current_user_id)) -> UserOut:
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    return _to_out(user)


@router.put("/password")
@limiter.limit(_LOGIN_RATE_LIMIT)
def change_password(req: ChangePasswordRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> dict:
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    if user.password_hash:
        if not req.current_password or not verify_password(req.current_password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    service.set_password(user.id, hash_password(req.new_password))
    return {"message": "Password updated"}
