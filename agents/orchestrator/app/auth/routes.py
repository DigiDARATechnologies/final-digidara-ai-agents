from fastapi import APIRouter, Depends, HTTPException, Request, status

import logging

from app.auth import email_verification, google_oauth, service
from app.auth.consent import CONSENT_POLICY_VERSION
from app.auth.schemas import (
    AccountDeleteRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    TwoStepChallenge,
    TwoStepLoginRequest,
    TwoStepResendRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.account import sign_ins, two_step
from app.auth.security import get_current_session, get_current_user_id, hash_password, verify_password
from app.models import User
from app.rate_limit import allow_account_attempt, limiter
from app import agent_data, job_data

logger = logging.getLogger("orchestrator.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

# Sign-in and sign-up carry no bearer token yet, so `limiter` counts them per
# IP. A college's students all share one address, so that count is loose; the
# real credential-stuffing / spam guard is the per-account limit below.
_LOGIN_IP_RATE_LIMIT = "120/minute"
_LOGIN_ACCOUNT_RATE_LIMIT = "5/minute"
_GOOGLE_RATE_LIMIT = "120/minute"
# Signed-in password changes are counted per user (bearer token).
_LOGIN_RATE_LIMIT = "5/minute"
_TOO_MANY_ATTEMPTS = "Too many attempts for this account. Please wait a minute and try again."
# Per account. Each send is an email; each verify is a guess at a 6-digit code
# (which also locks after 5 wrong tries).
_SEND_CODE_RATE_LIMIT = "5/hour"
_VERIFY_CODE_RATE_LIMIT = "10/minute"


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        mobile=user.mobile,
        is_admin=user.is_admin,
        consent_accepted_at=user.consent_accepted_at,
        consent_policy_version=user.consent_policy_version,
        email_verified=bool(user.email_verified),
        verification_required=not email_verification.is_verified(user),
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def signup(req: SignupRequest, request: Request) -> TokenResponse:
    email = req.email.strip().lower()
    if not allow_account_attempt("signup", email, _LOGIN_ACCOUNT_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
    if service.get_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = service.create_user(req.name.strip(), email, req.mobile, hash_password(req.password), CONSENT_POLICY_VERSION)
    if email_verification.verification_required():
        # Best effort: the account exists either way, and the verify screen
        # can always send another code.
        try:
            email_verification.send_code(user.id)
        except email_verification.VerificationError as exc:
            logger.warning("signup verification email not sent (%s)", exc.status_code)
    return TokenResponse(access_token=sign_ins.issue_token(user, request, "signup"), user=_to_out(user))


@router.post("/email/send-code")
@limiter.limit(_SEND_CODE_RATE_LIMIT)
def send_email_code(request: Request, user_id: str = Depends(get_current_user_id)) -> dict:
    """Email a new 6-digit verification code to the signed-in account."""
    try:
        email_verification.send_code(user_id)
    except email_verification.VerificationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"message": "We've sent a 6-digit code to your email."}


@router.post("/email/verify", response_model=UserOut)
@limiter.limit(_VERIFY_CODE_RATE_LIMIT)
def verify_email_code(req: VerifyEmailRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> UserOut:
    try:
        email_verification.verify_code(user_id, req.code)
    except email_verification.VerificationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    return _to_out(user)


@router.post("/password/forgot")
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def forgot_password(req: ForgotPasswordRequest, request: Request) -> dict:
    """Email a reset code. The answer is the same whether or not the email
    has an account, so this can't be used to look accounts up."""
    email = req.email.strip().lower()
    if not allow_account_attempt("reset-send", email, _SEND_CODE_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
    try:
        email_verification.send_reset_code(email)
    except email_verification.VerificationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"message": "If an account uses this email, we've sent it a 6-digit code."}


@router.post("/password/reset")
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def reset_password(req: ResetPasswordRequest, request: Request) -> dict:
    email = req.email.strip().lower()
    if not allow_account_attempt("reset-verify", email, _VERIFY_CODE_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
    try:
        email_verification.reset_password(email, req.code, hash_password(req.new_password))
    except email_verification.VerificationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"message": "Your password has been changed. Please log in with your new password."}


@router.post("/login", response_model=TokenResponse | TwoStepChallenge)
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def login(req: LoginRequest, request: Request) -> TokenResponse | TwoStepChallenge:
    if not allow_account_attempt("login", req.email, _LOGIN_ACCOUNT_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
    user = service.get_by_email(req.email.strip().lower())
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if two_step.is_enabled(user.id) and two_step.available():
        # The password was right; the session waits for the emailed code.
        try:
            two_step.send_code(user.id, force=True)
        except two_step.TwoStepError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        return TwoStepChallenge(challenge=two_step.challenge_for(user.id), email=two_step.mask_email(user.email))
    # Accounts made for someone (an organization's admin or learners) were
    # never sent a code at sign-up: the verify screen they land on needs one.
    email_verification.send_code_if_none_pending(user)
    return TokenResponse(access_token=sign_ins.issue_token(user, request, "password"), user=_to_out(user))


@router.post("/login/two-step", response_model=TokenResponse)
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def login_two_step(req: TwoStepLoginRequest, request: Request) -> TokenResponse:
    """The second step of a password sign-in: the code that was emailed."""
    try:
        user_id = two_step.user_for_challenge(req.challenge)
    except two_step.TwoStepError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    if not allow_account_attempt("two-step-login", user_id, _VERIFY_CODE_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
    try:
        two_step.check_code(user_id, req.code)
    except two_step.TwoStepError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    email_verification.send_code_if_none_pending(user)
    return TokenResponse(access_token=sign_ins.issue_token(user, request, "two_step"), user=_to_out(user))


@router.post("/login/two-step/resend")
@limiter.limit(_LOGIN_IP_RATE_LIMIT)
def login_two_step_resend(req: TwoStepResendRequest, request: Request) -> dict:
    try:
        user_id = two_step.user_for_challenge(req.challenge)
        if not allow_account_attempt("two-step-resend", user_id, _SEND_CODE_RATE_LIMIT):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY_ATTEMPTS)
        two_step.send_code(user_id)
    except two_step.TwoStepError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"message": "We've sent a new code."}


@router.post("/google", response_model=TokenResponse)
# Each call makes two outbound requests to Google with our client secret;
# unthrottled, it lets anyone burn that quota or hammer the code exchange.
# Per IP, and a college shares one address; every code is single-use and
# checked by Google, so there is no password to guess here.
@limiter.limit(_GOOGLE_RATE_LIMIT)
def google_auth(req: GoogleAuthRequest, request: Request) -> TokenResponse:
    profile = google_oauth.exchange_code(req.code, req.redirect_uri)

    user = service.get_by_google_id(profile.sub)
    if not user:
        existing = service.get_by_email(profile.email)
        if existing:
            user = service.link_google_id(existing.id, profile.sub)
        else:
            # A brand-new account. "Continue with Google" no longer needs the
            # consent box ticked first: without it the account records no
            # consent, and onboarding (consent_required) asks for the same
            # affirmative DPDP consent before any learner data is used.
            user = service.create_google_user(
                profile.name, profile.email, profile.sub, CONSENT_POLICY_VERSION if req.consent else None,
            )

    return TokenResponse(access_token=sign_ins.issue_token(user, request, "google"), user=_to_out(user))


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
    try:
        data["job_agent"] = job_data.export_user_data(user_id)
        data.update(agent_data.export_user_data(user_id, data["account"]["email"]))
    except (job_data.JobDataUnavailable, agent_data.AgentDataUnavailable) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return data


@router.put("/password")
@limiter.limit(_LOGIN_RATE_LIMIT)
def change_password(req: ChangePasswordRequest, request: Request, current: tuple[str, str | None] = Depends(get_current_session)) -> dict:
    user_id, session_id = current
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    if user.password_hash:
        if not req.current_password or not verify_password(req.current_password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    service.set_password(user.id, hash_password(req.new_password))
    # Every other device is now signed out; this one gets a fresh token.
    return {"message": "Password updated", "access_token": sign_ins.token_for_session(user.id, session_id)}


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
    try:
        agent_data.delete_user_data(user_id, user.email)
        job_data.delete_user_data(user_id)
    except (job_data.JobDataUnavailable, agent_data.AgentDataUnavailable) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    service.delete_user(user_id)
