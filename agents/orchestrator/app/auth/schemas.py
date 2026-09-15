from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    mobile: str | None = None
    password: str = Field(min_length=8, max_length=255)
    # DPDP Act 2023 requires a free, specific, informed, unambiguous
    # affirmative action -- not an implied "by continuing you agree".
    # `consent` must be an explicit `true` sent only after the user has
    # ticked the notice checkbox; the frontend gates the submit button on
    # this same value so there's no path to sending `false`, but we still
    # reject it server-side rather than trust the client.
    consent: bool = Field(...)

    @field_validator("consent")
    @classmethod
    def _consent_must_be_given(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the Privacy Policy and Terms of Service to create an account.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=255)


class GoogleAuthRequest(BaseModel):
    code: str = Field(min_length=1)
    # Must exactly match the redirect_uri used to obtain `code` — Google's
    # token endpoint rejects a mismatch. Sent by the frontend as
    # `${window.location.origin}/auth/google/callback`.
    redirect_uri: str = Field(min_length=1)
    # Same consent flag as SignupRequest, required only when this call ends
    # up creating a brand-new account (see routes.google_auth) -- an
    # existing user signing back in via Google already consented once.
    consent: bool = False


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    mobile: str | None
    is_admin: bool = False
    consent_accepted_at: datetime | None = None
    consent_policy_version: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AccountDeleteRequest(BaseModel):
    # Required for password accounts as a confirmation step, so a merely
    # stolen/leaked bearer token can't permanently erase an account on its
    # own. Google-only accounts (no password_hash) have nothing to check.
    password: str | None = None
