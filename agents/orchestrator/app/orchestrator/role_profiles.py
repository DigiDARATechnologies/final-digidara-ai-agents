"""Generate validated, user-facing AI role profiles."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.llm.client import call_text
from app.schemas import RoleProfileRequest, RoleProfileResponse

logger = logging.getLogger("orchestrator.role_profiles")

_SYSTEM_PROMPT = """You generate practical AI-assistant role profiles.
Return JSON only, with exactly these top-level fields: summary, skills, declaration.
declaration must contain capabilities, limitations, required_inputs, and
suggested_next_actions. Every list must have 3 to 8 short, specific strings.
Write for an AI assistant, not a human job applicant. Do not invent credentials,
real-world experience, legal authority, access to private systems, or the ability
to act without user authorization. Limitations must state when human review,
authorization, or specialist advice is needed."""


class RoleProfileGenerationError(RuntimeError):
    """The provider response could not be used as a role profile."""


def _json_from_model(text: str) -> dict:
    """Accept JSON and the common accidental Markdown code fence."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RoleProfileGenerationError("The model did not return valid JSON.") from exc
    if not isinstance(value, dict):
        raise RoleProfileGenerationError("The model returned a JSON value instead of an object.")
    return value


def generate_role_profile(request: RoleProfileRequest) -> RoleProfileResponse:
    context = request.context.strip() if request.context else "No additional context was supplied."
    user_prompt = (
        f"Target role: {request.target_role.strip()}\n"
        f"Context: {context}\n\n"
        "Create the profile now."
    )
    try:
        generated = _json_from_model(call_text(_SYSTEM_PROMPT, user_prompt, temperature=0.2))
        return RoleProfileResponse(target_role=request.target_role.strip(), **generated)
    except (RoleProfileGenerationError, ValidationError):
        logger.exception("invalid role-profile response for role=%r", request.target_role)
        raise RoleProfileGenerationError("The model returned an invalid role profile.") from None
    except Exception as exc:  # provider/network failures must not leak implementation detail
        logger.exception("role-profile generation failed for role=%r", request.target_role)
        raise RoleProfileGenerationError("The role profile could not be generated. Please retry.") from exc
