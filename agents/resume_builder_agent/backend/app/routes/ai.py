import json
import os
import re
import time
from urllib import error, request as url_request
import httpx

try:
    import anthropic
    from anthropic import Anthropic
except (ImportError, OSError):
    class _AnthropicUnavailable:
        class AuthenticationError(Exception):
            pass

        class RateLimitError(Exception):
            pass

        class APIConnectionError(Exception):
            pass

        class APIStatusError(Exception):
            status_code = 503

        class APIError(Exception):
            pass

    anthropic = _AnthropicUnavailable()
    Anthropic = None
from flask import Blueprint, current_app, jsonify, request
from app.security import rate_limit

ai_bp = Blueprint("ai", __name__)
MIN_RAW_INPUT_CHARS = 20
MAX_RAW_INPUT_CHARS = 8000
MAX_JOB_DESCRIPTION_CHARS = 30000
MAX_RESUME_JSON_CHARS = 200000
MAX_OPTIMIZER_JOB_DESCRIPTION_CHARS = 12000
MAX_OPTIMIZER_SOURCE_CHARS = 4000
STOP_WORDS = {
    "ability",
    "about",
    "and",
    "are",
    "for",
    "from",
    "have",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
    "work",
    "working",
}


class GroqRateLimitError(RuntimeError):
    """A provider quota response that should be surfaced as HTTP 429."""


class OpenAIRateLimitError(GroqRateLimitError):
    """OpenAI quota response surfaced consistently as HTTP 429."""


GROQ_RATE_LIMIT_MESSAGE = (
    "The AI service's rate limit was reached. Please wait about a minute and try again."
)
GROQ_SHORT_RETRY_SECONDS = 5


def error_response(message, status_code=400):
    return jsonify({"success": False, "message": message}), status_code


def get_text_response(message):
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    ).strip()


def get_ai_response_text(prompt, max_tokens=600):
    provider = os.environ.get("AI_PROVIDER", "").strip().lower()
    if provider in {"", "local"}:
        raise RuntimeError("AI provider is not configured")
    if provider == "groq":
        return create_groq_message(prompt, max_tokens=max_tokens)
    if provider == "openai":
        return create_openai_response(prompt, max_tokens=max_tokens)
    if provider == "anthropic":
        message = create_anthropic_message(prompt, max_tokens=max_tokens)
        return get_text_response(message)
    raise RuntimeError("AI_PROVIDER must be one of: 'openai', 'anthropic', or 'groq'")


def parse_ai_json(raw_text):
    """Extract the JSON object from an LLM response without accepting invalid data."""
    text = raw_text.strip() if isinstance(raw_text, str) else ""
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as initial_error:
        start = candidate.find("{")
        if start >= 0:
            depth = 0
            in_string = False
            escaped = False
            for index in range(start, len(candidate)):
                character = candidate[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False
                    continue
                if character == '"':
                    in_string = True
                elif character == "{":
                    depth += 1
                elif character == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(candidate[start:index + 1])
                        except json.JSONDecodeError:
                            break

        try:
            current_app.logger.warning(
                "Could not extract JSON from AI response (first 2000 chars): %r",
                raw_text[:2000] if isinstance(raw_text, str) else raw_text,
            )
        except RuntimeError:
            # The helper is also safe to call in isolated unit tests.
            pass
        raise initial_error


def get_ai_json_response(prompt, max_tokens=600):
    """Request and parse model JSON, with one targeted recovery for truncation."""
    try:
        return parse_ai_json(get_ai_response_text(prompt, max_tokens=max_tokens))
    except json.JSONDecodeError:
        current_app.logger.warning("AI response was incomplete; retrying once with JSON-only recovery prompt.")
        retry_prompt = (
            f"{prompt}\n\nIMPORTANT: Return one complete JSON object only. "
            "Do not add reasoning, markdown, or any text before or after the JSON."
        )
        return parse_ai_json(get_ai_response_text(retry_prompt, max_tokens=max_tokens))


def create_groq_message(prompt, max_tokens=600):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    model = os.environ.get("GROQ_MODEL")
    if not model:
        raise RuntimeError("GROQ_MODEL is not configured")

    request_payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    # GPT-OSS returns its reasoning separately. Keep it out of the answer and
    # use Groq's JSON mode so resume endpoints receive a JSON object directly.
    if model.startswith("openai/gpt-oss-"):
        request_payload.update(
            {
                "include_reasoning": False,
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            }
        )
    payload = json.dumps(request_payload).encode("utf-8")
    for attempt in range(2):
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                content=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            break
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or exc.response.reason_phrase
            if exc.response.status_code == 401:
                raise RuntimeError(f"Groq API authentication failed: {detail}") from exc
            if exc.response.status_code == 403:
                raise RuntimeError(f"Groq API access forbidden: {detail}") from exc
            if exc.response.status_code == 429:
                wait_seconds = groq_retry_wait_seconds(detail)
                if attempt == 0 and wait_seconds is not None and wait_seconds < GROQ_SHORT_RETRY_SECONDS:
                    time.sleep(wait_seconds)
                    continue
                raise GroqRateLimitError(GROQ_RATE_LIMIT_MESSAGE) from exc
            raise RuntimeError(f"Groq API returned status {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Could not connect to Groq API") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Groq API response did not include text") from exc


def create_openai_response(prompt, max_tokens=600):
    """Call OpenAI's Responses API using a server-side OPENAI_API_KEY."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    model = os.environ.get("OPENAI_MODEL")
    if not model:
        raise RuntimeError("OPENAI_MODEL is not configured")

    payload = json.dumps({
        "model": model,
        "input": prompt,
        "max_output_tokens": max_tokens,
        "store": False,
    }).encode("utf-8")
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            content=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or exc.response.reason_phrase
        if exc.response.status_code == 401:
            raise RuntimeError(f"OpenAI API authentication failed: {detail}") from exc
        if exc.response.status_code == 403:
            raise RuntimeError(f"OpenAI API access forbidden: {detail}") from exc
        if exc.response.status_code == 429:
            raise OpenAIRateLimitError("The OpenAI API rate limit was reached. Please wait and try again.") from exc
        raise RuntimeError(f"OpenAI API returned status {exc.response.status_code}: {detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Could not connect to OpenAI") from exc

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    try:
        return "".join(
            content["text"]
            for item in data["output"] if item.get("type") == "message"
            for content in item.get("content", []) if content.get("type") == "output_text"
        ).strip()
    except (KeyError, TypeError) as exc:
        raise RuntimeError("OpenAI API response did not include text") from exc


def groq_retry_wait_seconds(detail):
    """Return Groq's requested retry delay when its 429 body includes one."""
    match = re.search(r"please try again in\s+([0-9.]+)\s*(ms|milliseconds?|s|seconds?)\b", detail or "", re.I)
    if not match:
        return None
    wait = float(match.group(1))
    return wait / 1000 if match.group(2).lower().startswith("m") else wait


def read_groq_error_detail(exc):
    try:
        body = exc.read().decode("utf-8")
        data = json.loads(body)
        if isinstance(data.get("error"), dict):
            return data["error"].get("message") or body
        return data.get("message") or body
    except Exception:
        return exc.reason or "No error detail returned"


def experience_level_guidance(experience_level):
    if experience_level == "fresher":
        return "Emphasize academic projects, internships, coursework, and verified skills. Do not invent job titles, years of experience, or seniority."
    return "Emphasize quantified achievements, scope, and career impact when supported by the candidate-provided input."


def build_bullets_prompt(raw_input, role, industry, experience_level="experienced"):
    return f"""
Turn the raw experience notes into 3-4 polished, quantifiable resume bullet points.

Role: {role}
Industry: {industry}
Candidate experience level: {experience_level}
Raw input:
{raw_input}

Requirements:
- Make each bullet concise, achievement-focused, and suitable for a resume.
- Add realistic metrics only when they are clearly implied by the raw input.
- Do not invent employers, tools, certifications, dates, or unverifiable facts.
- Start each bullet with a strong action verb.
- {experience_level_guidance(experience_level)}
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"bullets": ["...", "..."]}}
""".strip()


def build_summary_prompt(resume, target_role, job_description=""):
    return f"""
Write one 2-3 sentence professional resume summary for exactly the target role.

Target role: {target_role}
Candidate experience level: {resume.get("experience_level") or "experienced"}
Job description:
{job_description or "Not provided. Use the target role and candidate resume context."}
Full resume JSON:
{json.dumps(resume, ensure_ascii=True)}

Requirements:
- Treat the target role above as the only role to optimize for, even if the resume JSON contains a different or multi-role title.
- Do not mention unrelated alternate target roles from the resume JSON.
- First identify the target role's likely skills, seniority, and domain expectations. Then select only the candidate's actual experience, skills, and projects that support those expectations.
- If a job description is provided, prioritize matching supported skills, tools, and responsibilities from it.
- Make the summary specific to the candidate's actual experience, skills, projects, and education.
- Keep it professional, concise, and suitable for the top of a resume.
- Do not invent employers, credentials, metrics, tools, dates, or unverifiable facts.
- {experience_level_guidance(resume.get("experience_level") or "experienced")}
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"summary": "..."}}
""".strip()


def build_skills_prompt(resume, target_role, job_description=""):
    return f"""
Create a concise, deduplicated skills list for exactly the target role.

Target role: {target_role}
Job description:
{job_description or "Not provided. Use the target role and candidate resume context."}
Full resume JSON:
{json.dumps(resume, ensure_ascii=True)}

Requirements:
- Include only skills directly evidenced by the candidate's existing skills, experience, projects, or education.
- Use the target role and job description only to prioritize supported skills; never add a tool or technology solely because it is common for the role or listed in the job description.
- Preserve useful existing skills where relevant and do not invent tools, certifications, or domain knowledge.
- Exclude generic soft skills and duplicate variants when stronger technical or domain skills are evidenced.
- Return at most 12 concise, ATS-relevant skill names with no duplicates.
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"skills": ["...", "..."]}}
""".strip()


def build_optimize_resume_prompt(resume, target_role, job_description, experience_entries, project_entries):
    """Build one grounded request for every field generated by optimize-resume.

    The candidate context appears once, with only rewriteable entries represented
    in the two indexed lists.  This keeps a complete generation within one Groq
    request instead of resending resume context for each individual entry.
    """
    # Uploaded notes are already carried in the indexed entries. Excluding the
    # full resume avoids duplicate text and non-content metadata in every call.
    context = {
        "personal_info": {key: (resume.get("personal_info") or {}).get(key) for key in ("name", "location")},
        "education": resume.get("education") or [],
        "skills": resume.get("skills") or [],
        "certifications": resume.get("certifications") or [],
        "achievements": resume.get("achievements") or [],
        "experience": experience_entries,
        "projects": project_entries,
    }
    experience_level = resume.get("experience_level") or "experienced"
    compact_job_description = re.sub(r"\s+", " ", job_description or "").strip()[:MAX_OPTIMIZER_JOB_DESCRIPTION_CHARS]
    return f"""
Generate a complete, truthful resume optimization for exactly the target role.

Target role: {target_role}
Candidate experience level: {experience_level}
Job description:
{compact_job_description or "Not provided. Use the target role and candidate resume context."}
Candidate context JSON (the indexed experience and project entries are the only entries to rewrite):
{json.dumps(context, ensure_ascii=True, separators=(",", ":"))}

Requirements:
- Treat the target role above as the only role to optimize for, even if the candidate context contains a different or multi-role title. Do not mention unrelated alternate target roles.
- The first sentence of the summary must contain the exact target role: "{target_role}". If the uploaded evidence is transferable rather than direct, describe the candidate as an aspiring or transition candidate for that role; do not claim unsupported direct experience.
- First identify the target role's likely skills, seniority, and domain expectations, then select only the candidate's actual experience, skills, projects, and education that support them. If a job description is provided, prioritize supported matching skills, tools, and responsibilities.
- Write a professional, concise 2-3 sentence summary specific to the candidate's actual experience, skills, projects, and education.
- Create at most 12 concise, deduplicated, ATS-relevant skills. Include only skills directly evidenced by the candidate context; never add a tool, certification, or domain knowledge solely because it is common for the role or listed in the job description. Exclude generic soft skills.
- For every indexed experience entry, turn its source notes into 3-4 concise, achievement-focused resume bullets. Start each bullet with a strong action verb. Add realistic metrics only when clearly implied by the source notes.
- For every indexed project entry, turn its source notes into 3-4 concise, ATS-friendly resume bullets. Start each bullet with a strong action verb.
- Keep education and certification records factually unchanged; they are extracted from the uploaded resume and retained in the generated draft.
- For each existing achievement, rewrite its description into one concise, evidence-backed achievement statement while preserving its index. Do not create achievements that are not evidenced in the candidate context.
- Write a concise standard declaration using the candidate's provided name and location only. Do not include a fake signature, place, or date.
- Do not invent employers, credentials, metrics, tools, dates, users, links, business outcomes, facts, or any other unverifiable claim.
- {experience_level_guidance(experience_level)}
- Return every provided experience and project index exactly once, preserving each index. Do not return entries that are not in the context.
- Respond with only one complete valid JSON object, with no markdown, reasoning, or extra text.
- JSON shape must be exactly: {{"summary": "...", "experience": [{{"index": 0, "bullets": ["...", "..."]}}], "projects": [{{"index": 0, "bullets": ["...", "..."]}}], "achievements": [{{"index": 0, "description": "..."}}], "skills": ["...", "..."], "declaration": "..."}}
""".strip()


def build_tailor_to_jd_prompt(resume_json, job_description):
    return f"""
Compare the resume JSON against the job description and suggest targeted resume improvements.

Resume JSON:
{json.dumps(resume_json, ensure_ascii=True)}

Job description:
{job_description}

Requirements:
- Identify important keywords, tools, skills, responsibilities, and domain terms from the job description that are relevant to the resume.
- Reword existing resume bullets to better align with the job description while preserving truthfulness.
- Do not invent employers, tools, credentials, metrics, dates, or experience that is not supported by the resume.
- Keep reworded bullets concise, resume-ready, and achievement-oriented.
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"suggested_keywords": ["..."], "reworded_bullets": ["..."]}}
""".strip()


def build_project_bullets_prompt(raw_input, title, technologies, experience_level="experienced"):
    return f"""
Turn the raw project notes into 3-4 ATS-friendly resume bullets.

Project title: {title}
Technologies: {technologies}
Candidate experience level: {experience_level}
Raw input:
{raw_input}

Requirements:
- Preserve only facts supported by the raw input.
- Do not invent metrics, tools, users, links, dates, or business outcomes.
- Start each bullet with a strong action verb.
- {experience_level_guidance(experience_level)}
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"bullets": ["...", "..."]}}
""".strip()


def build_improve_bullet_prompt(bullet, mode, context):
    return f"""
Improve this resume bullet without inventing unsupported facts.

Mode: {mode}
Context JSON:
{json.dumps(context, ensure_ascii=True)}
Bullet:
{bullet}

Requirements:
- Keep the claim truthful and resume-ready.
- Do not add metrics unless the original bullet or context clearly supports them.
- Respond with only valid JSON and no extra text.
- JSON shape must be exactly: {{"bullet": "...", "notes": ["..."]}}
""".strip()


def clean_bullet_text(value):
    return re.sub(r"^[\s\-*•]+", "", str(value or "")).strip()


def sanitize_bullets(values):
    seen = set()
    bullets = []
    for value in values or []:
        text = clean_bullet_text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        bullets.append(text)
    return bullets[:6]


def sanitize_skill_items(values):
    """Normalize model skill strings to the resume API's skill object shape."""
    seen = set()
    skills = []
    for value in values or []:
        text = value.get("skill_name") if isinstance(value, dict) else value
        text = str(text or "").strip()
        # Treat punctuation variants such as "Problem-Solving" and
        # "Problem Solving" as the same ATS skill.
        key = re.sub(r"[^a-z0-9]+", "", text.lower())
        if not text or key in seen:
            continue
        seen.add(key)
        skills.append({"skill_name": text})
    return skills[:16]


def ensure_target_role_in_summary(summary, target_role):
    """Keep an otherwise valid AI response visibly tied to the user-selected role."""
    normalized_summary = str(summary or "").strip()
    normalized_role = str(target_role or "").strip()
    if normalized_role and normalized_role.lower() not in normalized_summary.lower():
        return f"{normalized_role} candidate. {normalized_summary}"
    return normalized_summary


def role_alignment(resume, target_role):
    """Report whether the selected role is evidenced by the uploaded record."""
    role_terms = set(re.findall(r"[a-z]{3,}", str(target_role or "").lower()))
    source = json.dumps(resume, ensure_ascii=True).lower()
    matched = sorted(term for term in role_terms if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", source))
    if not role_terms or len(matched) == len(role_terms):
        return {"level": "direct", "message": "The selected target role is directly represented in the uploaded resume."}
    if matched:
        return {"level": "transferable", "message": "The selected role is only partly represented in the uploaded resume. The AI uses transferable evidence and does not invent missing experience."}
    return {"level": "limited", "message": "The uploaded resume does not contain direct evidence for the selected target role. Add truthful role-relevant skills, projects, or experience for a stronger match."}


def entry_source_text(item, fields):
    """Return the parsed, candidate-provided text available for an AI rewrite."""
    parts = []
    seen = set()
    for field in fields:
        value = item.get(field)
        values = value if isinstance(value, list) else [value]
        for entry in values:
            text = str(entry or "").strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                parts.append(text)
    return "\n".join(parts).strip()


def keyword_list(text, limit=18):
    words = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", text or "")
    seen = set()
    results = []
    for word in words:
        normalized = word.lower()
        if normalized in STOP_WORDS or normalized in seen:
            continue
        seen.add(normalized)
        results.append(word)
        if len(results) >= limit:
            break
    return results


def local_skill_suggestions(resume_json, job_description):
    existing = {skill.lower() for phrase in extract_resume_phrases(resume_json) for skill in split_skill_text(phrase)}
    suggested = [keyword for keyword in keyword_list(job_description, 24) if keyword.lower() not in existing]
    return {
        "skills": suggested[:16],
        "keywords": keyword_list(job_description, 18),
        "provider": "local_fallback",
        "note": "Suggestions are extracted from the job description. Add only skills you can defend.",
    }


def split_skill_text(value):
    text = str(value or "").strip()
    if not text:
        return []
    if ":" in text:
        text = text.split(":", 1)[1]
    return [item.strip() for item in text.split(",") if item.strip()]


def extract_resume_phrases(resume_json):
    phrases = []
    for skill in resume_json.get("skills", []):
        if isinstance(skill, dict) and skill.get("skill_name"):
            phrases.append(skill["skill_name"])
    for experience in resume_json.get("experience", []):
        if not isinstance(experience, dict):
            continue
        phrases.extend(experience.get("ai_generated_bullets") or [])
        if experience.get("raw_input"):
            phrases.append(experience["raw_input"])
    for project in resume_json.get("projects", []):
        if isinstance(project, dict):
            phrases.extend(filter(None, [project.get("title"), project.get("description")]))
    return phrases


def create_anthropic_message(prompt, max_tokens=600):
    if Anthropic is None:
        raise RuntimeError("Anthropic SDK is unavailable")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    model = os.environ.get("ANTHROPIC_MODEL")
    if not model:
        raise RuntimeError("ANTHROPIC_MODEL is not configured")

    client = Anthropic(api_key=api_key)
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )


@ai_bp.post("/ai/generate-bullets")
@rate_limit(20)
def generate_bullets():
    payload = request.get_json(silent=True) or {}
    raw_input = (payload.get("raw_input") or "").strip()
    role = (payload.get("role") or "").strip()
    industry = (payload.get("industry") or "").strip()

    missing = [
        field
        for field, value in {
            "raw_input": raw_input,
            "role": role,
            "industry": industry,
        }.items()
        if not value
    ]
    if missing:
        return error_response(f"Missing required field(s): {', '.join(missing)}", 400)
    if len(raw_input) < MIN_RAW_INPUT_CHARS:
        return error_response(
            f"raw_input must be at least {MIN_RAW_INPUT_CHARS} characters",
            400,
        )
    if len(raw_input) > MAX_RAW_INPUT_CHARS:
        return error_response(
            f"raw_input must not exceed {MAX_RAW_INPUT_CHARS} characters",
            413,
        )
    if len(role) > 255 or len(industry) > 255:
        return error_response("role and industry must not exceed 255 characters", 413)

    try:
        parsed = get_ai_json_response(
            build_bullets_prompt(raw_input, role, industry, payload.get("experience_level") or payload.get("experienceLevel") or "experienced"),
            max_tokens=600,
        )
        bullets = parsed.get("bullets")

        if not isinstance(bullets, list) or not all(
            isinstance(bullet, str) for bullet in bullets
        ):
            return error_response("AI response did not include valid bullets", 502)

        return jsonify({"bullets": bullets, "provider": parsed.get("provider", "ai")}), 200
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)
    except anthropic.AuthenticationError:
        return error_response("Anthropic API authentication failed", 401)
    except anthropic.RateLimitError:
        return error_response("Anthropic API rate limit exceeded", 429)
    except anthropic.APIConnectionError:
        return error_response("Could not connect to Anthropic API", 503)
    except anthropic.APIStatusError as exc:
        return error_response(
            f"Anthropic API returned status {exc.status_code}",
            502,
        )
    except anthropic.APIError:
        return error_response("Anthropic API request failed", 502)


@ai_bp.post("/ai/tailor-to-jd")
@rate_limit(15)
def tailor_to_jd():
    payload = request.get_json(silent=True) or {}
    resume_json = payload.get("resume_json")
    job_description = (payload.get("job_description") or "").strip()

    missing = []
    if not resume_json:
        missing.append("resume_json")
    if not job_description:
        missing.append("job_description")
    if missing:
        return error_response(f"Missing required field(s): {', '.join(missing)}", 400)
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        return error_response(
            f"job_description must not exceed {MAX_JOB_DESCRIPTION_CHARS} characters",
            413,
        )
    if len(json.dumps(resume_json, ensure_ascii=True)) > MAX_RESUME_JSON_CHARS:
        return error_response("resume_json is too large", 413)

    try:
        parsed = get_ai_json_response(
            build_tailor_to_jd_prompt(resume_json, job_description),
            max_tokens=700,
        )
        suggested_keywords = parsed.get("suggested_keywords")
        reworded_bullets = parsed.get("reworded_bullets")

        if not isinstance(suggested_keywords, list) or not all(
            isinstance(keyword, str) for keyword in suggested_keywords
        ):
            return error_response(
                "AI response did not include valid suggested_keywords",
                502,
            )
        if not isinstance(reworded_bullets, list) or not all(
            isinstance(bullet, str) for bullet in reworded_bullets
        ):
            return error_response(
                "AI response did not include valid reworded_bullets",
                502,
            )

        return jsonify(
            {
                "suggested_keywords": suggested_keywords,
                "reworded_bullets": reworded_bullets,
                "provider": parsed.get("provider", "ai"),
                "note": parsed.get("note"),
            }
        ), 200
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)
    except anthropic.AuthenticationError:
        return error_response("Anthropic API authentication failed", 401)
    except anthropic.RateLimitError:
        return error_response("Anthropic API rate limit exceeded", 429)
    except anthropic.APIConnectionError:
        return error_response("Could not connect to Anthropic API", 503)
    except anthropic.APIStatusError as exc:
        return error_response(
            f"Anthropic API returned status {exc.status_code}",
            502,
        )
    except anthropic.APIError:
        return error_response("Anthropic API request failed", 502)


@ai_bp.post("/ai/generate-project-bullets")
@rate_limit(20)
def generate_project_bullets():
    payload = request.get_json(silent=True) or {}
    raw_input = (payload.get("raw_input") or "").strip()
    title = (payload.get("title") or "").strip()
    technologies = (payload.get("technologies") or "").strip()

    if not raw_input:
        return error_response("Missing required field(s): raw_input", 400)
    if len(raw_input) < MIN_RAW_INPUT_CHARS:
        return error_response(f"raw_input must be at least {MIN_RAW_INPUT_CHARS} characters", 400)
    if len(raw_input) > MAX_RAW_INPUT_CHARS:
        return error_response(f"raw_input must not exceed {MAX_RAW_INPUT_CHARS} characters", 413)

    try:
        parsed = get_ai_json_response(build_project_bullets_prompt(raw_input, title, technologies, payload.get("experience_level") or payload.get("experienceLevel") or "experienced"), max_tokens=600)
        bullets = sanitize_bullets(parsed.get("bullets"))
        if not bullets:
            return error_response("AI response did not include valid bullets", 502)
        return jsonify({"bullets": bullets, "provider": parsed.get("provider", "ai")}), 200
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)


@ai_bp.post("/ai/improve-bullet")
@rate_limit(30)
def improve_bullet():
    payload = request.get_json(silent=True) or {}
    bullet = clean_bullet_text(payload.get("bullet"))
    mode = (payload.get("mode") or "improve").strip()
    context = payload.get("context") or {}

    if not bullet:
        return error_response("Missing required field(s): bullet", 400)
    if len(bullet) > 1000:
        return error_response("bullet must not exceed 1000 characters", 413)
    if mode not in {"improve", "shorten", "technical", "metric_suggestion"}:
        return error_response("mode must be improve, shorten, technical, or metric_suggestion", 400)

    try:
        parsed = get_ai_json_response(build_improve_bullet_prompt(bullet, mode, context), max_tokens=350)
        improved = clean_bullet_text(parsed.get("bullet"))
        if not improved:
            return error_response("AI response did not include a valid bullet", 502)
        return jsonify({
            "bullet": improved,
            "notes": parsed.get("notes") if isinstance(parsed.get("notes"), list) else [],
            "provider": parsed.get("provider", "ai"),
        }), 200
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)


@ai_bp.post("/ai/suggest-skills")
@rate_limit(20)
def suggest_skills():
    payload = request.get_json(silent=True) or {}
    resume_json = payload.get("resume_json") or {}
    job_description = (payload.get("job_description") or "").strip()

    if not job_description:
        return error_response("Missing required field(s): job_description", 400)
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        return error_response(f"job_description must not exceed {MAX_JOB_DESCRIPTION_CHARS} characters", 413)

    data = local_skill_suggestions(resume_json, job_description)
    return jsonify(data), 200


@ai_bp.post("/ai/analyze-job-description")
@rate_limit(20)
def analyze_job_description():
    payload = request.get_json(silent=True) or {}
    job_description = (payload.get("job_description") or "").strip()

    if not job_description:
        return error_response("Missing required field(s): job_description", 400)
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        return error_response(f"job_description must not exceed {MAX_JOB_DESCRIPTION_CHARS} characters", 413)

    keywords = keyword_list(job_description, 24)
    return jsonify({
        "keywords": keywords,
        "must_have": keywords[:8],
        "nice_to_have": keywords[8:16],
        "missing_information": [
            "Exact metrics and scope should come from your verified experience, not the job description."
        ],
        "provider": "local_fallback",
    }), 200


@ai_bp.post("/ai/generate-declaration")
@rate_limit(20)
def generate_declaration():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "the candidate").strip()
    location = (payload.get("location") or "").strip()
    place = f" in {location}" if location else ""
    return jsonify({
        "declaration": (
            f"I, {name}, hereby declare that the information provided in this resume is true and correct "
            f"to the best of my knowledge and belief{place}."
        ),
        "provider": "local_fallback",
    }), 200


@ai_bp.post("/ai/generate-summary")
@rate_limit(20)
def generate_summary():
    payload = request.get_json(silent=True) or {}
    target_role = (
        payload.get("target_role")
        or payload.get("targetRole")
        or payload.get("target_job_title")
        or payload.get("targetJobTitle")
        or payload.get("role")
        or payload.get("jobTitle")
        or ""
    ).strip()
    job_description = (
        payload.get("job_description")
        or payload.get("jobDescription")
        or payload.get("target_job_description")
        or payload.get("targetJobDescription")
        or ""
    ).strip()
    resume = payload.get("resume")

    if "resume" not in payload:
        resume = {key: value for key, value in payload.items() if key not in {
            "target_role", "targetRole", "target_job_title", "targetJobTitle", "role", "jobTitle",
            "job_description", "jobDescription", "target_job_description", "targetJobDescription",
        }}

    missing = []
    if not target_role:
        missing.append("target_role")
    if not resume:
        missing.append("resume")
    if missing:
        if missing == ["target_role"]:
            return error_response("Target job title is required.", 400)
        return error_response(f"Missing required field(s): {', '.join(missing)}", 400)
    if len(target_role) > 255:
        return error_response("target_role must not exceed 255 characters", 413)
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        return error_response(f"job_description must not exceed {MAX_JOB_DESCRIPTION_CHARS} characters", 413)
    if len(json.dumps(resume, ensure_ascii=True)) > MAX_RESUME_JSON_CHARS:
        return error_response("resume is too large", 413)

    try:
        parsed = get_ai_json_response(
            build_summary_prompt(resume, target_role, job_description),
            max_tokens=500,
        )
        summary = parsed.get("summary")

        if not isinstance(summary, str) or not summary.strip():
            return error_response("AI response did not include a valid summary", 502)

        return jsonify(
            {
                "summary": summary.strip(),
                "provider": parsed.get("provider", "ai"),
                "note": parsed.get("note"),
            }
        ), 200
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)
    except anthropic.AuthenticationError:
        return error_response("Anthropic API authentication failed", 401)
    except anthropic.RateLimitError:
        return error_response("Anthropic API rate limit exceeded", 429)
    except anthropic.APIConnectionError:
        return error_response("Could not connect to Anthropic API", 503)
    except anthropic.APIStatusError as exc:
        return error_response(
            f"Anthropic API returned status {exc.status_code}",
            502,
        )
    except anthropic.APIError:
        return error_response("Anthropic API request failed", 502)


@ai_bp.post("/ai/optimize-resume")
# A single resume optimization can take long enough that users may retry after
# a network interruption. Keep the normal per-minute AI abuse protection, but
# do not lock a user out after five attempts.
@rate_limit(20)
def optimize_resume():
    """Generate a fully AI-optimized version of a resume: summary plus bullets for
    every experience and project entry that has enough raw input to work with.
    Reuses the same prompt builders and truthfulness rules as the single-field AI
    actions above. Never falls back to canned/template content - any AI failure
    (missing key, auth failure, invalid response, etc.) returns a specific error
    instead of partially- or fully-fabricated resume content.
    """
    payload = request.get_json(silent=True) or {}
    resume = payload.get("resume")
    target_role = (
        payload.get("target_role")
        or payload.get("targetRole")
        or ""
    ).strip()
    job_description = (
        payload.get("job_description")
        or payload.get("jobDescription")
        or ""
    ).strip()

    if not isinstance(resume, dict) or not resume:
        return error_response("Missing required field(s): resume", 400)
    if len(json.dumps(resume, ensure_ascii=True)) > MAX_RESUME_JSON_CHARS:
        return error_response("resume is too large", 413)
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        return error_response(f"job_description must not exceed {MAX_JOB_DESCRIPTION_CHARS} characters", 413)

    resolved_role = target_role or (resume.get("target_role") or resume.get("title") or "").strip()
    if not resolved_role:
        return error_response("target_role is required", 400)
    if len(resolved_role) > 255:
        return error_response("target_role must not exceed 255 characters", 413)

    try:
        optimized = dict(resume)
        skipped = []
        generated = {
            "summary": False,
            "skills": 0,
            "education": len(resume.get("education") or []),
            "certifications": len(resume.get("certifications") or []),
            "experience": 0,
            "projects": 0,
            "achievements": 0,
            "declaration": False,
        }
        experience = []
        experience_requests = []
        for index, item in enumerate(resume.get("experience") or []):
            item = dict(item)
            source_text = entry_source_text(
                item,
                ("raw_input", "ai_generated_bullets", "bullets", "description", "responsibilities", "achievements"),
            )
            if len(source_text) >= MIN_RAW_INPUT_CHARS:
                entry_context = dict(item)
                for field in ("raw_input", "ai_generated_bullets", "bullets", "description", "responsibilities", "achievements"):
                    entry_context.pop(field, None)
                experience_requests.append({
                    "index": index,
                    "entry": entry_context,
                    "role": (item.get("role") or resolved_role).strip(),
                    "industry": (item.get("industry") or resolved_role).strip(),
                    "source_notes": source_text[:MAX_OPTIMIZER_SOURCE_CHARS],
                })
            else:
                skipped.append({
                    "section": "experience",
                    "index": index,
                    "reason": "No usable experience content was available to rewrite.",
                })
            experience.append(item)
        optimized["experience"] = experience

        projects = []
        project_requests = []
        for index, item in enumerate(resume.get("projects") or []):
            item = dict(item)
            source_text = entry_source_text(
                item,
                ("raw_input", "description", "ai_generated_bullets", "bullets", "details", "highlights"),
            )
            if len(source_text) >= MIN_RAW_INPUT_CHARS:
                entry_context = dict(item)
                for field in ("raw_input", "description", "ai_generated_bullets", "bullets", "details", "highlights"):
                    entry_context.pop(field, None)
                project_requests.append({
                    "index": index,
                    "entry": entry_context,
                    "title": (item.get("title") or item.get("name") or "").strip(),
                    "technologies": (item.get("technologies") or "").strip(),
                    "source_notes": source_text[:MAX_OPTIMIZER_SOURCE_CHARS],
                })
            else:
                skipped.append({
                    "section": "projects",
                    "index": index,
                    "reason": "No usable project content was available to rewrite.",
                })
            projects.append(item)

        parsed = get_ai_json_response(
            build_optimize_resume_prompt(
                resume, resolved_role, job_description, experience_requests, project_requests
            ),
            # A full multi-entry resume needs room for summary, skills, and all
            # bullets. One generous response is still far below the former
            # repeated-context N+2 request pattern for normal resumes.
            max_tokens=3000,
        )
        summary = parsed.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            return error_response("AI response did not include a valid summary", 502)
        optimized["summary"] = ensure_target_role_in_summary(summary, resolved_role)
        generated["summary"] = True
        generated_skills = sanitize_skill_items(parsed.get("skills"))
        optimized["skills"] = generated_skills or sanitize_skill_items(resume.get("skills"))
        generated["skills"] = len(optimized["skills"])

        for section, requested_entries, output_entries in (
            ("experience", experience_requests, experience),
            ("projects", project_requests, projects),
        ):
            responses = parsed.get(section)
            by_index = {}
            expected_indices = {entry["index"] for entry in requested_entries}
            for response_item in responses if isinstance(responses, list) else []:
                if not isinstance(response_item, dict) or not isinstance(response_item.get("index"), int):
                    continue
                index = response_item["index"]
                bullets = response_item.get("bullets")
                cleaned_bullets = sanitize_bullets(bullets) if isinstance(bullets, list) and all(isinstance(bullet, str) for bullet in bullets) else []
                if index in expected_indices and index not in by_index and cleaned_bullets:
                    by_index[index] = cleaned_bullets
            for index, bullets in by_index.items():
                output_entries[index]["ai_generated_bullets"] = by_index[index]
            generated[section] = len(by_index)
            for index in sorted(expected_indices - set(by_index)):
                skipped.append({
                    "section": section,
                    "index": index,
                    "reason": "AI did not return usable rewritten bullets; the original uploaded text was retained.",
                })

        optimized["projects"] = projects

        achievements = [dict(item) for item in (resume.get("achievements") or [])]
        achievement_responses = parsed.get("achievements", [])
        by_index = {}
        if isinstance(achievement_responses, list):
            next_index = 0
            for item in achievement_responses:
                if isinstance(item, dict):
                    index = item.get("index")
                    description = item.get("description")
                    if not isinstance(index, int):
                        index = next((candidate for candidate in range(next_index, len(achievements)) if candidate not in by_index), None)
                elif isinstance(item, str):
                    index = next((candidate for candidate in range(next_index, len(achievements)) if candidate not in by_index), None)
                    description = item
                else:
                    continue
                if not isinstance(index, int) or not isinstance(description, str):
                    continue
                description = description.strip()
                if index < 0 or index >= len(achievements) or index in by_index or not description:
                    continue
                by_index[index] = description
                next_index = index + 1
        for index, description in by_index.items():
            achievements[index]["description"] = description
        generated["achievements"] = len(by_index)
        for index in range(len(achievements)):
            if index not in by_index:
                skipped.append({
                    "section": "achievements",
                    "index": index,
                    "reason": "AI did not return a usable achievement rewrite; the original text was retained.",
                })
        optimized["achievements"] = achievements

        declaration = parsed.get("declaration")
        if isinstance(declaration, str) and declaration.strip():
            optimized["declaration"] = declaration.strip()
            generated["declaration"] = True

        return jsonify({
            "resume": optimized,
            "provider": "ai",
            "skipped": skipped,
            "generated": generated,
            "role_alignment": role_alignment(resume, resolved_role),
        }), 200
    except GroqRateLimitError as exc:
        return error_response(str(exc), 429)
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except json.JSONDecodeError:
        return error_response("AI response was not valid JSON", 502)
    except anthropic.AuthenticationError:
        return error_response("Anthropic API authentication failed", 401)
    except anthropic.RateLimitError:
        return error_response("Anthropic API rate limit exceeded", 429)
    except anthropic.APIConnectionError:
        return error_response("Could not connect to Anthropic API", 503)
    except anthropic.APIStatusError as exc:
        return error_response(
            f"Anthropic API returned status {exc.status_code}",
            502,
        )
    except anthropic.APIError:
        return error_response("Anthropic API request failed", 502)
