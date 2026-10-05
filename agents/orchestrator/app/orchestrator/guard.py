"""Code-level guards around the general chat. The router prompt tells the model
to stay on DigiDARA topics and resist prompt injection; these checks don't
rely on the model obeying:

- an obvious injection attempt gets a fixed reply without reaching the model;
- a reply that leaks the instructions (it contains the canary) is replaced;
- only agents actually registered right now can be connected to;
- browser-supplied history is trimmed and stripped of injection attempts.
"""
from __future__ import annotations

import re

# Embedded in the system prompt and nowhere else. If it ever shows up in a
# reply, the model is repeating its instructions.
CANARY = "DD-GUARD-7f3a91"

MAX_HISTORY_TURNS = 12

OFF_LIMITS_REPLY = (
    "I can only help with the **DigiDARA platform and its agents**. "
    "Ask me what an agent does, how to use it, or tell me what you want to practise and I'll connect you."
)

_INJECTION_PATTERNS = [
    r"\bignore\b.{0,40}\b(instruction|instructions|rules|prompt|above|previous|prior)\b",
    r"\bdisregard\b.{0,40}\b(instruction|instructions|rules|prompt|above|previous|prior)\b",
    r"\bforget\b.{0,40}\b(instruction|instructions|rules|prompt)\b",
    r"\b(system|developer|hidden|initial|original)\s+(prompt|message|instructions?)\b",
    # Asking for the assistant's OWN instructions, or for secrets -- not "show
    # me the instructions for Capstone", which is a normal question.
    r"\b(reveal|show|print|repeat|output|display|leak|tell\s+me)\b.{0,30}\byour\s+(system\s+)?(prompt|instructions|rules|configuration|guidelines)\b",
    r"\b(api[\s_-]?key|secret[\s_-]?key|access[\s_-]?token|environment\s+variables?)\b",
    r"(?:^|[\s'\"`])\.env\b",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\b.{0,30}\b(different|another|unrestricted|unfiltered|evil|jailbroken)\b",
    r"\b(developer|god|dan|jailbreak|unrestricted)\s+mode\b",
    r"\bjailbreak\b",
    r"\bpretend\b.{0,30}\b(no|without)\s+(rules|restrictions|limits)\b",
    r"\bnew\s+(instructions|rules|persona)\b",
    r"\boverride\b.{0,30}\b(instructions|rules|safety|policy)\b",
    r"</?\s*(system|assistant|instructions)\s*>",
    r"\[\s*(system|inst)\s*\]",
    r"^\s*(system|assistant)\s*:",
]
_INJECTION = re.compile("|".join(f"(?:{pattern})" for pattern in _INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text or ""))


def leaks_instructions(reply: str) -> bool:
    return CANARY.lower() in (reply or "").lower()


def safe_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """The last few turns, as plain user/assistant text, minus any turn that
    tries to inject instructions. Roles are already restricted by the request
    schema; this keeps a forged turn from steering the model regardless."""
    turns = [
        {"role": turn["role"], "content": turn["content"]}
        for turn in (history or [])
        if turn.get("role") in {"user", "assistant"} and not looks_like_injection(turn.get("content", ""))
    ]
    return turns[-MAX_HISTORY_TURNS:]
