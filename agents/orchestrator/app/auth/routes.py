from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import google_oauth, service
from app.auth.consent import CONSENT_POLICY_VERSION
from app.auth.schemas import (
    AccountDeleteRequest,
    GoogleAuthRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from app.auth.security import create_access_token, get_current_user_id, hash_password, verify_password
from app.models import User
from app.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Neither route carries a bearer token yet, so `limiter`'s key function
# falls back to per-IP — exactly what a credential-stuffing / signup-spam
# guard on these two routes needs.
_LOGIN_RATE_LIMIT = "5/minute"


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        mobile=user.mobile,
        consent_accepted_at=user.consent_accepted_at,
        consent_policy_version=user.consent_policy_version,
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit(_LOGIN_RATE_LIMIT)
def signup(req: SignupRequest, request: Request) -> TokenResponse:
    email = req.email.strip().lower()
    if service.get_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = service.create_user(req.name.strip(), email, req.mobile, hash_password(req.password), CONSENT_POLICY_VERSION)
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
        if existing:
            user = service.link_google_id(existing.id, profile.sub)
        else:
            # Creating a brand-new account -- DPDP Act 2023 requires the
            # same affirmative consent as the password signup path. The
            # frontend gates the "Continue with Google" button on the same
            # checkbox used for the signup form, so this should never fire
            # for a real user, but we still refuse server-side.
            if not req.consent:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "You must accept the Privacy Policy and Terms of Service to create an account.",
                )
            user = service.create_google_user(profile.name, profile.email, profile.sub, CONSENT_POLICY_VERSION)

    return TokenResponse(access_token=create_access_token(user.id), user=_to_out(user))


@router.get("/me", response_model=UserOut)
def me(user_id: str = Depends(get_current_user_id)) -> UserOut:
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    return _to_out(user)


@router.get("/me/export")
def export_my_data(user_id: str = Depends(get_current_user_id)) -> dict:
    """DPDP Act 2023 right to access: every piece of personal data this
    service holds about the caller, as a downloadable JSON document."""
    data = service.export_user_data(user_id)
    if data is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    return data


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(req: AccountDeleteRequest, user_id: str = Depends(get_current_user_id)) -> None:
    """DPDP Act 2023 right to erasure, and the mechanism for withdrawing
    consent -- since every processing this platform does is grounded in the
    consent captured at signup, withdrawing it and continuing to hold an
    account are contradictory, so deletion is how withdrawal is exercised.

    Password accounts must re-confirm their password so a merely leaked
    bearer token can't permanently erase the account on its own; Google-only
    accounts (no password_hash) have nothing to check.
    """
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    if user.password_hash:
        if not req.password or not verify_password(req.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")
    service.delete_user(user_id)
