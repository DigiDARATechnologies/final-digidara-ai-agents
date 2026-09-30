"""One conversational turn of the Resume Builder chat.

The chat's step-by-step parsers handle plain answers. Everything else -- an
edit of something said earlier ("change my PG college to ABC"), an answer in
a shape the parsers don't know ("UG - B.Com from XYZ College 2019 to 2022"),
or a correction to a value that failed ("the date is jan 2022") -- comes here.
The model reads the draft so far, what the chat last asked, the recent
conversation and the candidate's long-term memories (mem0, see
app/services/memory.py), and returns the draft fields to change.

The model's output is never trusted as-is: only known draft fields are
accepted, each is type-checked and trimmed, and dates are normalised.
"""
from __future__ import annotations

import json
from datetime import date

from flask import Blueprint, jsonify, request

from app.routes.ai import error_response, get_ai_json_response
from app.routes.resumes import get_request_user_id, lenient_month_year, parse_month_year
from app.security import rate_limit
from app.services import memory

chat_turn_bp = Blueprint("chat_turn", __name__)

INTENTS = {"answer", "edit", "question", "other"}
SCALAR_FIELDS = {"title", "name", "email", "phone", "location", "targetRole", "summary"}
STRING_LIST_FIELDS = {"skills", "links"}
SECTION_FIELDS = {
    "experience": ({"company", "role"}, {"start_date", "end_date", "raw_input"}, {"is_current"}),
    "education": ({"school"}, {"degree", "level", "field", "start_date", "end_date", "cgpa", "percentage"}, set()),
    "projects": ({"title"}, {"description"}, set()),
    "certifications": ({"name"}, {"issuer", "issue_date", "expiry_date", "credential_id", "credential_url", "description"}, set()),
    "achievements": ({"title"}, {"description", "date", "organization"}, set()),
}
DATE_KEYS = {"start_date", "end_date", "issue_date", "expiry_date", "date"}
MAX_TEXT = 4000
MAX_ITEMS = 30
MAX_HISTORY = 16


def _text(value, limit=MAX_TEXT):
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value).strip()[:limit] or None


def _normalise_date(value):
    """A readable date becomes "Jan 2022" (or a bare year); anything else is
    kept as written, so the create step can name it if it is still wrong."""
    text = _text(value, 40)
    if not text:
        return None
    if text.lower() in {"present", "current", "ongoing", "now"}:
        return "Present"
    if len(text) == 4 and text.isdigit():
        return text
    parsed = parse_month_year(text) or lenient_month_year(text)
    if isinstance(parsed, date):
        return parsed.strftime("%b %Y")
    return text


def _clean_section(name, items):
    required, optional, flags = SECTION_FIELDS[name]
    cleaned = []
    for item in items[:MAX_ITEMS] if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        entry = {}
        for key in required | optional:
            value = _normalise_date(item.get(key)) if key in DATE_KEYS else _text(item.get(key))
            if value:
                entry[key] = value
        for key in flags:
            if isinstance(item.get(key), bool):
                entry[key] = item[key]
        if all(entry.get(key) for key in required):
            cleaned.append(entry)
    return cleaned


def clean_updates(raw):
    """Keeps only known draft fields, each in the shape the chat expects."""
    if not isinstance(raw, dict):
        return {}
    updates = {}
    for key, value in raw.items():
        if key in SCALAR_FIELDS:
            text = _text(value)
            if text:
                updates[key] = text
        elif key == "experienceLevel" and value in {"fresher", "experienced"}:
            updates[key] = value
        elif key in STRING_LIST_FIELDS and isinstance(value, list):
            updates[key] = [text for text in (_text(item, 300) for item in value[:MAX_ITEMS * 2]) if text]
        elif key in SECTION_FIELDS and isinstance(value, list):
            updates[key] = _clean_section(key, value)
    return updates


def build_prompt(message, step, asked, draft, history, memories):
    memory_block = "\n".join(f"- {item}" for item in memories) or "(none)"
    history_block = "\n".join(
        f"{turn.get('role', 'user').upper()}: {str(turn.get('text', ''))[:600]}" for turn in history[-MAX_HISTORY:]
    ) or "(none)"
    return f"""You are the Resume Builder assistant for DigiDARA. A candidate is building their resume in a chat.
Understand their NEW MESSAGE and return the resume draft fields it adds or changes.

WHAT THE CHAT LAST ASKED (step "{step}"): {asked or "nothing specific"}

CURRENT DRAFT (the single source of truth for what is already saved):
{json.dumps(draft, ensure_ascii=False)}

WHAT YOU REMEMBER ABOUT THIS CANDIDATE (from earlier chats; use only to resolve references like
"same college as before", never to add facts the candidate did not give):
{memory_block}

RECENT CONVERSATION:
{history_block}

NEW MESSAGE: {message}

Decide the intent:
- "answer": the message answers what the chat last asked.
- "edit": the message changes something already in the draft ("change my college to ...", "the date is
  Jan 2022", "remove the second project", "my PG is MCA not MBA").
- "question": the candidate asks something; answer it in "reply" and change nothing.
- "other": anything else; say briefly what you can help with in "reply".

Rules:
- Never invent facts. Use only what the candidate wrote (or clearly referred to).
- Draft fields: title, name, email, phone, location, targetRole, summary, experienceLevel ("fresher" or
  "experienced"), skills (list of strings), links (list of URLs), and the lists
  experience [{{company, role, start_date, end_date, is_current}}],
  education [{{school, degree, level ("UG", "PG", "Diploma", "Doctorate", "12th", "10th"), field, start_date,
  end_date, cgpa, percentage}}], projects [{{title, description}}], certifications [{{name, issuer, issue_date}}],
  achievements [{{title, description, date}}].
- Several education entries may come in one message, separated by ";", new lines, or "UG ..." / "PG ...":
  make one entry each. B.Com, B.Sc, BCA, B.E., B.Tech, BBA, B.A., B.Pharm, MBBS, LLB etc. are UG;
  M.Com, M.Sc, MCA, M.E., M.Tech, MBA, M.A. etc. are PG.
- For a list field, return the COMPLETE updated list: keep every existing entry that did not change.
- Write dates as a month and year ("Jan 2022") or a year ("2022"); fix obvious typos like "janm2022".
- Return only fields that change; "updates" is {{}} for a question.
- "reply": one or two short, friendly sentences saying exactly what you changed (name the field and
  new value), or the answer to their question.

OUTPUT (strict JSON only):
{{"intent": "answer|edit|question|other", "updates": {{...}}, "reply": "..."}}"""


@chat_turn_bp.post("/ai/chat-turn")
@rate_limit(40)
def chat_turn():
    payload = request.get_json(silent=True) or {}
    message = _text(payload.get("message"), 3000)
    if not message:
        return error_response("message is required", 400)
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    history = [turn for turn in payload.get("history") or [] if isinstance(turn, dict)]
    user_id = get_request_user_id(payload)
    memories = memory.recall(user_id, message)

    try:
        parsed = get_ai_json_response(
            build_prompt(message, _text(payload.get("step"), 60) or "", _text(payload.get("asked"), 600), draft, history, memories),
            max_tokens=2500,
        )
    except (RuntimeError, json.JSONDecodeError) as exc:
        return error_response(f"The assistant could not read that message: {exc}", 502)

    intent = parsed.get("intent") if parsed.get("intent") in INTENTS else "other"
    updates = clean_updates(parsed.get("updates")) if intent in {"answer", "edit"} else {}
    reply = _text(parsed.get("reply"), 800) or ""
    memory.remember(user_id, [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ])
    return jsonify({"success": True, "intent": intent, "updates": updates, "reply": reply, "memories_used": len(memories)})


WORDING_FIELDS = {
    "summary": "professional summary (2-3 sentences)",
    "project": "project description (1-2 sentences)",
    "experience": "description of this role's work (1-3 short sentences or bullet-style lines)",
}


@chat_turn_bp.post("/ai/suggest-wording")
@rate_limit(30)
def suggest_wording():
    """A stronger, ATS-friendly wording of what the candidate just wrote, for
    them to accept or ignore while building the resume in the chat. Never adds
    facts: no invented numbers, tools, employers or results. suggestion=null
    when the text is already good or the model's answer is unusable."""
    payload = request.get_json(silent=True) or {}
    field = payload.get("field")
    text = str(payload.get("text") or "").strip()
    if field not in WORDING_FIELDS:
        return error_response(f"field must be one of: {', '.join(WORDING_FIELDS)}", 400)
    if not text:
        return error_response("text is required", 400)
    if len(text) > 3000:
        return error_response("text must not exceed 3000 characters", 413)
    role = str(payload.get("target_role") or "").strip()[:120]
    try:
        parsed = get_ai_json_response(
            f"""You are a resume writing assistant. Rewrite the candidate's {WORDING_FIELDS[field]} so it reads as
professional, concise and ATS-friendly{f' for a {role} role' if role else ''}.

Candidate's text: {json.dumps(text)}

Rules:
- Keep every fact exactly as given. Do NOT add numbers, percentages, tools, employers, dates or results
  that are not in the candidate's text.
- Use strong action verbs and plain language; no first person ("I", "my"), no buzzword filler.
- Keep it about the same length or shorter.
- If the text is already strong, return it unchanged.

Return strict JSON: {{"suggestion": "..."}}""",
            max_tokens=400,
        )
    except (RuntimeError, json.JSONDecodeError):
        return jsonify({"suggestion": None}), 200
    suggestion = str(parsed.get("suggestion") or "").strip()
    unchanged = " ".join(suggestion.lower().split()) == " ".join(text.lower().split())
    if not suggestion or unchanged or len(suggestion) > 1500:
        return jsonify({"suggestion": None}), 200
    return jsonify({"suggestion": suggestion}), 200
