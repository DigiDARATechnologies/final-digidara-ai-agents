"""Session tokens for the Strategy F invoke adapter (routes/invoke.py).

This module's original REST API has no login system of its own -- every
route takes a plain integer `student_id` wherever it needs one, straight
from the request body or URL, with nothing to stop one caller from acting
as another student. That's fine for the module in isolation, but not once
it's reachable through the shared DigiDARA gateway.

`ensure_session` mints a short-lived JWT the moment the gateway hands us a
gateway-verified caller identity (`X-DigiDARA-User-ID`) plus that learner's
email; every other action must present that JWT, and the adapter uses the
`student_id` embedded in it -- never one a client supplies -- for any
identity-scoped call it forwards to the real routes below.
"""
from __future__ import annotations

import os
import time

import jwt

JWT_SECRET = os.environ.get("SESSION_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("SESSION_JWT_TTL_SECONDS", "43200"))
JWT_AUDIENCE = "mock-interview-agent"
JWT_ISSUER = "digidara-gateway"


def issue_session_token(student_id: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(student_id),
            "iat": now,
            "exp": now + JWT_TTL_SECONDS,
            "aud": JWT_AUDIENCE,
            "iss": JWT_ISSUER,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


class InvalidSessionToken(Exception):
    pass


def student_id_from_token(token: str) -> int:
    if not token:
        raise InvalidSessionToken("sessionToken is required")
    try:
        claims = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE, issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "iat", "aud", "iss"]},
        )
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidSessionToken("Invalid or expired session") from exc
