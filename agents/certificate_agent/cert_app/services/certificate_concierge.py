"""LLM interpretation for natural-language certificate management requests."""
from __future__ import annotations

import json
import re
from typing import Dict

from langchain_openai import ChatOpenAI

from cert_app.config import get_settings
from cert_app.services.usage_service import record_llm_usage


def _json_object(raw: str) -> Dict:
    cleaned = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def interpret_certificate_request(message: str, context: str | None = None) -> Dict:
    """Classify learner intent without relying on frontend keyword rules."""
    settings = get_settings()
    phase = context or "request"
    prompt = f"""You are CertifyAI's certificate concierge. Interpret the learner's message naturally.

Conversation phase: {phase}
Learner message: {message!r}

Return only JSON. For phase 'request', intent must be one of:
- rename_certificate (they want a different name printed on a certificate)
- email_certificate (they want the PDF sent by email)
- download_certificate
- list_certificates
- unknown

For a name or email confirmation phase, intent must be one of:
- confirm
- revise
- cancel

Include a concise, learner-friendly `reply` only for `unknown`. Do not invent a name or email address. Do not perform any action; this is interpretation only.
Schema: {{"intent":"...","reply":"..."}}"""
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=120,
        )
        response = llm.invoke(prompt)
        record_llm_usage("certificate_concierge", response)
        result = _json_object(str(response.content))
        allowed = {"confirm", "revise", "cancel"} if phase.endswith("confirmation") else {
            "rename_certificate", "email_certificate", "download_certificate", "list_certificates", "unknown"
        }
        if result.get("intent") in allowed:
            return result
    except Exception:
        pass
    return {
        "intent": "unknown",
        "reply": "I can help you update the name on a certificate, download it, or email it. What would you like to do?",
    }
