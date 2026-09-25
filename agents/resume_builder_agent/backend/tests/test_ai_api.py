import json
import httpx

from app.routes import ai
from app.services.import_review import parse_resume_text


class FakeGroqResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"summary": "Ready."}'}}]}


def test_groq_provider_returns_chat_completion_text(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["timeout"] = kwargs["timeout"]
        captured["body"] = json.loads(kwargs["content"].decode("utf-8"))
        return FakeGroqResponse()

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(ai.httpx, "post", fake_post)

    text = ai.create_groq_message("Return JSON", max_tokens=25)

    assert text == '{"summary": "Ready."}'
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["timeout"] == 30
    assert captured["body"]["model"] == "openai/gpt-oss-20b"
    assert captured["body"]["messages"][0]["content"] == "Return JSON"
    assert captured["body"]["max_tokens"] == 25
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["reasoning_effort"] == "low"
    assert captured["body"]["include_reasoning"] is False


def test_openai_provider_returns_responses_api_output(monkeypatch):
    captured = {}

    class FakeOpenAIResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": '{"summary": "Ready."}'}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        captured["timeout"] = kwargs["timeout"]
        captured["body"] = json.loads(kwargs["content"].decode("utf-8"))
        return FakeOpenAIResponse()

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(ai.httpx, "post", fake_post)

    assert ai.get_ai_response_text("Return JSON", max_tokens=25) == '{"summary": "Ready."}'
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["timeout"] == 45
    assert captured["body"] == {
        "model": "gpt-4o-mini",
        "input": "Return JSON",
        "max_output_tokens": 25,
        "store": False,
    }


def test_openai_provider_requires_openai_environment_variables(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    try:
        ai.create_openai_response("Return JSON")
        assert False
    except RuntimeError as exc:
        assert str(exc) == "OPENAI_API_KEY is not configured"


def test_groq_forbidden_error_includes_response_detail(monkeypatch):
    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(
            403,
            request=request,
            json={"error": {"message": "Project is not allowed to use this model."}},
        )
        raise httpx.HTTPStatusError("Forbidden", request=request, response=response)

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(ai.httpx, "post", fake_post)

    try:
        ai.create_groq_message("Return JSON")
        assert False
    except RuntimeError as exc:
        message = str(exc)
        assert "Groq API access forbidden" in message
        assert "Project is not allowed" in message


def test_groq_short_rate_limit_wait_retries_once_and_succeeds(monkeypatch):
    calls = []
    sleeps = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            request = httpx.Request("POST", url)
            response = httpx.Response(
                429,
                request=request,
                json={"error": {"message": "Rate limit reached. Please try again in 659.999999ms."}},
            )
            raise httpx.HTTPStatusError("Rate limited", request=request, response=response)
        return FakeGroqResponse()

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    monkeypatch.setattr(ai.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert ai.create_groq_message("Return JSON") == '{"summary": "Ready."}'
    assert len(calls) == 2
    assert sleeps == [0.659999999]


def test_groq_long_rate_limit_wait_surfaces_friendly_message(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        response = httpx.Response(
            429,
            request=request,
            json={"error": {"message": "Rate limit reached. Please try again in 12s."}},
        )
        raise httpx.HTTPStatusError("Rate limited", request=request, response=response)

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(ai.httpx, "post", fake_post)

    try:
        ai.create_groq_message("Return JSON")
        assert False
    except ai.GroqRateLimitError as exc:
        assert str(exc) == ai.GROQ_RATE_LIMIT_MESSAGE
        assert "Rate limit reached. Please try again" not in str(exc)
    assert len(calls) == 1


def test_groq_failed_short_rate_limit_retry_surfaces_friendly_message(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        response = httpx.Response(
            429,
            request=request,
            json={"error": {"message": "Rate limit reached. Please try again in 100ms."}},
        )
        raise httpx.HTTPStatusError("Rate limited", request=request, response=response)

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    monkeypatch.setattr(ai.time, "sleep", lambda seconds: None)

    try:
        ai.create_groq_message("Return JSON")
        assert False
    except ai.GroqRateLimitError as exc:
        assert str(exc) == ai.GROQ_RATE_LIMIT_MESSAGE
    assert len(calls) == 2


def test_parse_ai_json_accepts_markdown_fenced_response():
    parsed = ai.parse_ai_json('```json\n{"summary": "Ready."}\n```')

    assert parsed == {"summary": "Ready."}


def test_parse_ai_json_extracts_json_after_reasoning_preamble():
    parsed = ai.parse_ai_json('Let me think about that first.\n\n{"bullets": ["Built dashboards."]}\nDone.')

    assert parsed == {"bullets": ["Built dashboards."]}


def test_generate_summary_keeps_invalid_ai_json_as_502(client, monkeypatch):
    monkeypatch.setattr(ai, "get_ai_response_text", lambda prompt, max_tokens: "No JSON was returned.")

    response = client.post(
        "/api/ai/generate-summary",
        json={"target_role": "Data Analyst", "resume": {"skills": [{"skill_name": "Python"}]}} ,
    )

    assert response.status_code == 502
    assert response.get_json()["message"] == "AI response was not valid JSON"


def test_tailor_to_jd_returns_error_when_groq_is_forbidden(client, monkeypatch):
    def forbidden_response(prompt, max_tokens):
        raise RuntimeError("Groq API access forbidden: Forbidden")

    monkeypatch.setattr(ai, "get_ai_response_text", forbidden_response)

    response = client.post(
        "/api/ai/tailor-to-jd",
        json={
            "resume_json": {
                "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
                "experience": [
                    {
                        "raw_input": "Built Python dashboards for business intelligence teams.",
                        "ai_generated_bullets": [],
                    }
                ],
                "projects": [],
            },
            "job_description": "Looking for Python, SQL, dashboards, and analytics.",
        },
    )

    assert response.status_code == 500
    assert "Groq API access forbidden" in response.get_json()["message"]


def test_generate_summary_returns_ai_response_on_success(client, monkeypatch):
    def fake_ai_response(prompt, max_tokens):
        return json.dumps({"summary": "Data Analyst with strong Python and SQL experience."})

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)

    response = client.post(
        "/api/ai/generate-summary",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
                "projects": [{"title": "Sales Dashboard"}],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["provider"] == "ai"
    assert payload["summary"] == "Data Analyst with strong Python and SQL experience."


def test_generate_summary_returns_error_when_groq_is_forbidden(client, monkeypatch):
    def forbidden_response(prompt, max_tokens):
        raise RuntimeError("Groq API access forbidden: Forbidden")

    monkeypatch.setattr(ai, "get_ai_response_text", forbidden_response)

    response = client.post(
        "/api/ai/generate-summary",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
                "projects": [{"title": "Sales Dashboard"}],
            },
        },
    )

    assert response.status_code == 500
    assert "Groq API access forbidden" in response.get_json()["message"]


def test_generate_summary_returns_error_when_ai_provider_is_unconfigured(client, monkeypatch):
    def missing_config_response(prompt, max_tokens):
        raise RuntimeError("GROQ_API_KEY is not configured")

    monkeypatch.setattr(ai, "get_ai_response_text", missing_config_response)

    response = client.post(
        "/api/ai/generate-summary",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "skills": [{"skill_name": "Power BI"}, {"skill_name": "SQL"}],
                "projects": [],
            },
        },
    )

    assert response.status_code == 500
    assert response.get_json()["message"] == "GROQ_API_KEY is not configured"


def test_generate_bullets_rejects_empty_raw_input(client):
    response = client.post(
        "/api/ai/generate-bullets",
        json={
            "raw_input": "",
            "role": "Software Engineer",
            "industry": "SaaS",
        },
    )

    assert response.status_code == 400
    assert "raw_input" in response.get_json()["message"]


def test_generate_bullets_accepts_a_thin_but_nonempty_source(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({"bullets": ["Built API endpoints."]}),
    )
    response = client.post(
        "/api/ai/generate-bullets",
        json={
            "raw_input": "Built APIs",
            "role": "Software Engineer",
            "industry": "SaaS",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["bullets"] == ["Built API endpoints."]


def test_generate_summary_requires_resume_and_target_role(client):
    response = client.post(
        "/api/ai/generate-summary",
        json={"target_role": "", "resume": {}},
    )

    assert response.status_code == 400
    assert "target_role" in response.get_json()["message"]
    assert "resume" in response.get_json()["message"]


def test_tailor_to_jd_requires_resume_and_job_description(client):
    response = client.post(
        "/api/ai/tailor-to-jd",
        json={"resume_json": {}, "job_description": ""},
    )

    assert response.status_code == 400
    assert "resume_json" in response.get_json()["message"]
    assert "job_description" in response.get_json()["message"]


def test_resume_edit_returns_a_reviewable_proposal_without_mutating_identity(client, monkeypatch):
    def fake_ai_response(prompt, max_tokens):
        assert "Candidate request:" in prompt
        assert max_tokens == 3500
        return json.dumps({
            "proposed_resume": {
                "id": 999,
                "user_id": "wrong-user",
                "summary": "Concise, evidence-based software engineer summary.",
                "skills": [{"skill_name": "Python"}],
            },
            "changes": ["Shortened the professional summary.", "Kept the supported Python skill."],
            "warnings": ["Review the wording before applying it."],
        })

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)
    response = client.post(
        "/api/ai/suggest-resume-edit",
        json={
            "edit_request": "Make my summary shorter.",
            "resume": {
                "id": 42,
                "user_id": "test-user",
                "title": "My resume",
                "summary": "Long existing summary.",
                "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
                "education": [{"school": "Example University"}],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["requires_confirmation"] is True
    assert payload["resume"]["id"] == 42
    assert payload["resume"]["user_id"] == "test-user"
    assert payload["resume"]["summary"] == "Concise, evidence-based software engineer summary."
    assert payload["resume"]["education"] == [{"school": "Example University"}]


def test_resume_edit_requires_a_nonempty_request(client):
    response = client.post("/api/ai/suggest-resume-edit", json={"resume": {"summary": "Existing"}})

    assert response.status_code == 400
    assert response.get_json()["message"] == "edit_request is required"


def test_optimize_resume_returns_ai_generated_summary_and_bullets(client, monkeypatch):
    def fake_ai_response(prompt, max_tokens):
        assert "complete, truthful resume optimization" in prompt
        assert max_tokens == 3000
        return json.dumps({
            "summary": "Data Analyst skilled in Python and SQL.",
            "skills": ["Python", "SQL", "Power BI"],
            "experience": [{"index": 0, "bullets": ["Built dashboards using Python and SQL."]}],
            "projects": [{"index": 0, "bullets": ["Built a sales analytics dashboard in Power BI."]}],
        })

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)

    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
                "experience": [
                    {
                        "company": "Example Analytics",
                        "role": "Data Analyst Intern",
                        "raw_input": "Built 12 KPI reports for operations stakeholders using Python and SQL.",
                        "ai_generated_bullets": [],
                    }
                ],
                "projects": [
                    {
                        "title": "Sales Analytics Dashboard",
                        "technologies": "Power BI, SQL",
                        "raw_input": "Created a dashboard for revenue, region, and category analysis.",
                        "ai_generated_bullets": [],
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["provider"] == "ai"
    optimized = payload["resume"]
    assert optimized["summary"] == "Data Analyst skilled in Python and SQL."
    assert optimized["skills"] == [
        {"skill_name": "Python"},
        {"skill_name": "SQL"},
        {"skill_name": "Power BI"},
    ]
    assert optimized["experience"][0]["ai_generated_bullets"] == ["Built dashboards using Python and SQL."]
    assert optimized["projects"][0]["ai_generated_bullets"] == [
        "Built a sales analytics dashboard in Power BI."
    ]
    assert payload["generated"] == {
        "summary": True,
        "skills": 3,
        "education": 0,
        "certifications": 0,
        "experience": 1,
        "projects": 1,
        "achievements": 0,
        "declaration": False,
    }


def test_optimize_resume_writes_the_selected_role_and_keeps_recommendations_out_of_skills(client, monkeypatch):
    def fake_ai_response(prompt, max_tokens):
        assert "Target role: Data Analyst" in prompt
        assert '"skills":[{"skill_name":"Python"' in prompt
        return json.dumps({
            "summary": "Data Analyst candidate with verified Python and SQL skills.",
            "skills": ["SQL", "DAX", "Python"],
            "experience": [],
            "projects": [],
            "role_analysis": {
                "matched_skills": ["Python", "SQL", "Power BI", "Excel"],
                "recommended_skills_to_learn": ["DAX"],
                "missing_information": ["Examples of data-analysis work"],
            },
        })

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)
    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "target_role": "Python Web Developer",
                "skills": [
                    {"skill_name": "Python"}, {"skill_name": "SQL"},
                    {"skill_name": "Power BI"}, {"skill_name": "Excel"},
                ],
                "experience": [{"role": "Python Web Developer", "company": "Acme", "raw_input": "Developed web applications using Python."}],
                "education": [{"degree": "B.Tech", "field": "Computer Science", "school": "Anna University", "end_date": "2024"}],
                "projects": [],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["resume"]["target_role"] == "Data Analyst"
    assert payload["resume"]["experience"][0]["role"] == "Python Web Developer"
    assert [item["skill_name"] for item in payload["resume"]["skills"]] == ["SQL", "Python", "Power BI", "Excel"]
    assert payload["role_analysis"]["recommended_skills_to_learn"] == ["DAX"]
    assert "DAX" not in [item["skill_name"] for item in payload["resume"]["skills"]]


def test_optimize_resume_applies_grounded_achievement_and_declaration_content(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({
            "summary": "Grounded summary.",
            "skills": ["SQL"],
            "experience": [],
            "projects": [],
            "achievements": [{"index": 0, "description": "Recognized for improving verified reporting quality."}],
            "declaration": "I declare that the information in this resume is true to the best of my knowledge.",
        }),
    )

    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "skills": [{"skill_name": "SQL"}],
                "experience": [],
                "projects": [],
                "achievements": [{"title": "Reporting award", "description": "Improved reporting quality."}],
            },
        },
    )

    assert response.status_code == 200
    optimized = response.get_json()["resume"]
    assert optimized["achievements"][0]["title"] == "Reporting award"
    assert optimized["achievements"][0]["description"] == "Recognized for improving verified reporting quality."
    assert optimized["declaration"].startswith("I declare")


def test_optimize_resume_retains_achievement_when_ai_returns_an_unusable_shape(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({
            "summary": "Grounded summary.",
            "skills": ["SQL"],
            "experience": [],
            "projects": [],
            "achievements": {"description": "Unexpected object shape"},
        }),
    )

    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {"achievements": [{"title": "Reporting award", "description": "Original verified achievement."}]},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["resume"]["achievements"][0]["description"] == "Original verified achievement."
    assert payload["generated"]["achievements"] == 0
    assert payload["skipped"] == [{
        "section": "achievements",
        "index": 0,
        "reason": "AI did not return a usable achievement rewrite; the original text was retained.",
    }]


def test_optimize_resume_uses_one_llm_call_for_all_usable_uploaded_entries(client, monkeypatch):
    # Parse real upload-style text so this covers the fields produced by the
    # import pipeline: experience uses raw_input while projects use description.
    parsed_resume, _ = parse_resume_text(
        """Alex Morgan
DATA ANALYST

Experience
Data Analyst - Example Analytics
- Built KPI reports for operations teams using SQL and Python every week.
- Reduced manual reporting time by thirty percent through automation.
Business Analyst - Sample Company
- Analyzed customer trends and delivered dashboards for business leaders.
- Prepared weekly performance reports with validated sales data.

Projects
Revenue Dashboard
Created a Power BI dashboard for regional revenue and product performance analysis.
Added SQL data models and automated refresh checks for accurate reporting.
Customer Insights Tool
Built a Python analysis tool to identify customer retention and engagement trends.
Presented findings through charts and concise stakeholder reports.
"""
    )
    calls = []

    def fake_ai_response(prompt, max_tokens):
        calls.append(prompt)
        assert "complete, truthful resume optimization" in prompt
        return json.dumps({
            "summary": "AI summary",
            "skills": ["Python", "SQL", "Power BI"],
            "experience": [
                {"index": index, "bullets": [f"AI experience bullet {index}"]}
                for index in range(len(parsed_resume["experience"]))
            ],
            "projects": [
                {"index": index, "bullets": [f"AI project bullet {index}"]}
                for index in range(len(parsed_resume["projects"]))
            ],
        })

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)
    response = client.post(
        "/api/ai/optimize-resume",
        json={"target_role": "Data Analyst", "resume": parsed_resume},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert len(calls) == 1
    assert payload["resume"]["summary"] == "Data Analyst candidate. AI summary"
    assert {skill["skill_name"] for skill in payload["resume"]["skills"]} >= {"Python", "SQL", "Power BI"}
    assert all(item["ai_generated_bullets"] for item in payload["resume"]["experience"])
    assert all(item["ai_generated_bullets"] for item in payload["resume"]["projects"])
    assert payload["skipped"] == []


def test_optimize_resume_keeps_original_project_when_ai_omits_its_bullets(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({
            "summary": "Data Analyst candidate with project experience.",
            "skills": ["SQL"],
            "experience": [],
            "projects": [],
        }),
    )
    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {
                "projects": [{
                    "title": "Sales Dashboard",
                    "description": "Built a reporting dashboard from verified sales data using SQL.",
                }],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["resume"]["projects"][0]["ai_generated_bullets"] == ["Built a reporting dashboard from verified sales data using SQL."]
    assert payload["generated"]["projects"] == 1
    assert payload["skipped"] == []


def test_optimize_resume_turns_thin_source_notes_into_bullets_not_raw_paragraphs(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({
            "summary": "Candidate with verified web development project experience.",
            "skills": ["React JS"],
            "experience": [{"index": 0, "bullets": ["Developed a Swiggy website."]}],
            "projects": [{"index": 0, "bullets": ["Built the project with React JS."]}],
        }),
    )
    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Frontend Developer",
            "resume": {
                "experience": [{"company": "Student Project", "role": "Developer", "raw_input": "i developed a swiggy website"}],
                "projects": [{"title": "Food Delivery UI", "description": "react js"}],
            },
        },
    )

    assert response.status_code == 200
    resume = response.get_json()["resume"]
    assert resume["experience"][0]["ai_generated_bullets"]
    assert resume["projects"][0]["ai_generated_bullets"]
    assert resume["experience"][0]["ai_generated_bullets"] != ["i developed a swiggy website"]
    assert resume["projects"][0]["ai_generated_bullets"] != ["react js"]


def test_optimize_resume_reports_entries_without_usable_content(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: json.dumps({
            "summary": "AI summary", "skills": [], "experience": [], "projects": []
        }),
    )
    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {"experience": [{"role": "Analyst"}], "projects": [{"title": "Portfolio"}]},
        },
    )

    assert response.status_code == 200
    assert response.get_json()["skipped"] == [
        {"section": "experience", "index": 0, "reason": "No usable experience content was available to rewrite."},
        {"section": "projects", "index": 0, "reason": "No usable project content was available to rewrite."},
    ]


def test_optimize_resume_returns_error_when_ai_unavailable(client, monkeypatch):
    def missing_config_response(prompt, max_tokens):
        raise RuntimeError("GROQ_API_KEY is not configured")

    monkeypatch.setattr(ai, "get_ai_response_text", missing_config_response)

    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {"skills": [{"skill_name": "Python"}], "experience": [], "projects": []},
        },
    )

    assert response.status_code == 500
    assert response.get_json()["message"] == "GROQ_API_KEY is not configured"


def test_optimize_resume_returns_429_when_groq_token_limit_is_reached(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_ai_response_text",
        lambda prompt, max_tokens: (_ for _ in ()).throw(
            ai.GroqRateLimitError(ai.GROQ_RATE_LIMIT_MESSAGE)
        ),
    )

    response = client.post(
        "/api/ai/optimize-resume",
        json={
            "target_role": "Data Analyst",
            "resume": {"skills": [{"skill_name": "Python"}], "experience": [], "projects": []},
        },
    )

    assert response.status_code == 429
    assert response.get_json()["message"] == ai.GROQ_RATE_LIMIT_MESSAGE


def test_optimize_resume_requires_resume_and_target_role(client):
    response = client.post("/api/ai/optimize-resume", json={"resume": {}})

    assert response.status_code == 400
