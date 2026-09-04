"""Server-side half of the Google "Sign in with Google" authorization-code
flow. The frontend only ever sees GOOGLE_CLIENT_ID (public) and redirects the
browser to Google directly; GOOGLE_CLIENT_SECRET stays here and is only used
to exchange a one-time `code` for tokens over a direct server-to-server HTTPS
call — that direct call is what we trust, so there's no need to separately
verify the id_token's signature."""
import os

import httpx
from fastapi import HTTPException, status

TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleProfile:
    def __init__(self, sub: str, email: str, email_verified: bool, name: str):
        self.sub = sub
        self.email = email
        self.email_verified = email_verified
        self.name = name


def _credentials() -> tuple[str, str]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured.")
    return client_id, client_secret


def exchange_code(code: str, redirect_uri: str) -> GoogleProfile:
    client_id, client_secret = _credentials()
    try:
        token_response = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach Google to complete sign-in.") from exc
    if token_response.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google sign-in could not be completed. Please try again.")
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google did not return an access token.")

    try:
        userinfo_response = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach Google to fetch your profile.") from exc
    if userinfo_response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google did not return profile information.")
    info = userinfo_response.json()

    sub = info.get("sub")
    email = info.get("email")
    if not sub or not email:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google profile is missing required fields.")
    if not info.get("email_verified", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your Google email is not verified.")

    return GoogleProfile(sub=sub, email=email.strip().lower(), email_verified=True, name=info.get("name") or email.split("@")[0])
