from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    mobile: str | None = None
    password: str = Field(min_length=8, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    code: str = Field(min_length=1)
    # Must exactly match the redirect_uri used to obtain `code` — Google's
    # token endpoint rejects a mismatch. Sent by the frontend as
    # `${window.location.origin}/auth/google/callback`.
    redirect_uri: str = Field(min_length=1)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    mobile: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
