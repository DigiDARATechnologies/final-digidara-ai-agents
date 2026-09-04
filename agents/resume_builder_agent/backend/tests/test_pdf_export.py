import builtins
from copy import deepcopy
from io import BytesIO

from pypdf import PdfReader

from app.services import pdf_export


def comprehensive_resume_payload():
    """Shared long-form fixture for catalog-wide PDF layout regression checks."""
    bullets = [
        "Delivered a multi-region analytics workflow with documented controls, clear stakeholder updates, and measurable reliability improvements across a long-running release cycle.",
        "Partnered with engineering and operations teams to turn ambiguous requirements into tested, accessible dashboards and repeatable reporting processes.",
    ]
    return {
        "title": "Senior Platform Analytics and Delivery Specialist Resume",
        "target_role": "Senior Data Analyst",
        "summary": "Evidence-led analytics professional who translates complex operational data into reliable decisions for technical and non-technical teams.",
        "personal_info": {"name": "Alexandra Morgan-Smith", "email": "alexandra@example.com", "phone": "+1 555 0100", "location": "Remote", "links": ["LinkedIn: linkedin.com/in/alexandra", "GitHub: github.com/alexandra"]},
        "experience": [
            {"company": f"Northstar Systems {index}", "role": "Analytics Lead", "start_date": f"202{index}-01-01", "end_date": "2025-12-31", "ai_generated_bullets": bullets}
            for index in range(1, 4)
        ],
        "projects": [
            {"title": f"Operations Visibility Platform {index}", "description": "Technologies: Python, SQL, Power BI\n" + bullets[0], "ai_generated_bullets": bullets}
            for index in range(1, 4)
        ],
        "education": [
            {"school": "Example University", "degree": "MSc", "field": "Data Analytics", "start_date": "2018", "end_date": "2020"},
            {"school": "State College", "degree": "BSc", "field": "Information Systems", "start_date": "2014", "end_date": "2018"},
        ],
        "skills": [{"skill_name": skill} for skill in ["Python", "SQL", "Power BI", "Tableau", "Statistics", "Data Modeling", "ETL", "Stakeholder Management", "Accessibility", "AWS", "Git", "React"]],
        "languages": [{"language_name": "English", "proficiency": "Fluent"}, {"language_name": "Spanish", "proficiency": "Intermediate"}],
        "certifications": [{"name": "Cloud Practitioner", "issuer": "Example Cloud", "date": "2024-06-01"}],
        "publications": [],  # Must be skipped by every template with no empty heading or gap.
        "achievements": [],
    }


def test_pdf_normalizes_broken_dash_characters_and_uses_only_candidate_declaration(sample_resume_payload):
    payload = deepcopy(sample_resume_payload)
    payload["summary"] = "Hands\u2011on, AI\u2013driven analysis for real\u2011time dashboards."
    payload["skills"] = [{"skill_name": "IoT\u2011enabled analytics"}]
    payload["declaration"] = (
        "I declare that the information above is correct.\n"
        "Signature: Swetha S"
    )

    pdf_bytes = pdf_export.render_resume_pdf(payload, "steady-form")
    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)

    assert "Hands-on, AI-driven analysis for real-time dashboards." in extracted
    assert "IoT-enabled analytics" in extracted
    assert "Arun Kuma" not in extracted
    assert "DD/MM/YYYY" not in extracted
    assert extracted.count("DECLARATION") == 1
    assert "Signature: Swetha S" in extracted


def test_pdf_includes_projects_and_their_ai_generated_bullets(sample_resume_payload):
    sample_resume_payload["projects"] = [{
        "title": "Project Atlas",
        "description": "Built the original project prototype.",
        "ai_generated_bullets": ["Designed a reliable analytics workflow."],
    }]

    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "steady-form")
    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)

    assert "PROJECTS" in extracted
    assert "Project Atlas" in extracted
    assert "Designed a reliable analytics workflow." in extracted
    assert extracted.index("EXPERIENCE") < extracted.index("PROJECTS") < extracted.index("EDUCATION")


def test_precision_ats_pdf_uses_the_reference_single_column_alignment(sample_resume_payload):
    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "steady-form")
    positions = {}

    def collect(text, cm, tm, _font, _size):
        if text.strip() == "PROFESSIONAL SUMMARY":
            positions["summary"] = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]

    PdfReader(BytesIO(pdf_bytes)).pages[0].extract_text(visitor_text=collect)

    assert pdf_export.template_style_spec("steady-form")["section_alignment"] == "left"
    assert positions["summary"] >= 72


def test_pdf_export_falls_back_when_weasyprint_native_libs_are_missing(
    monkeypatch,
    sample_resume_payload,
):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("native library missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "modern")

    assert pdf_bytes.startswith(b"%PDF")


def test_classic_pdf_fallback_uses_classic_template_text(
    monkeypatch,
    sample_resume_payload,
):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("native library missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "classic")

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1500


def test_pdf_export_has_builtin_fallback_when_pdf_libraries_are_missing(
    monkeypatch,
    sample_resume_payload,
):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint" or name.startswith("reportlab"):
            raise ImportError("pdf library missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "modern")

    assert pdf_bytes.startswith(b"%PDF")
    assert b"Demo User" in pdf_bytes


def test_pdf_export_with_long_resume_content(client, monkeypatch, sample_resume_payload):
    long_text = "Led cross-functional delivery of platform improvements. " * 120
    sample_resume_payload["summary"] = long_text
    sample_resume_payload["experience"][0]["raw_input"] = long_text
    sample_resume_payload["experience"][0]["ai_generated_bullets"] = [
        "Delivered platform improvements across APIs, dashboards, and workflow tooling."
    ]

    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]
    captured = {}

    def fake_render_resume_pdf(resume_data, template_choice):
        captured["resume_data"] = resume_data
        captured["template_choice"] = template_choice
        return b"%PDF-1.4\n% test pdf bytes\n"

    monkeypatch.setattr(
        "app.routes.resumes.render_resume_pdf",
        fake_render_resume_pdf,
    )

    response = client.post(
        f"/api/resume/{created['id']}/export",
        json={"template_choice": "modern", "user_id": "test-user"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-1.4")
    assert captured["template_choice"] == "mercury-flow"
    assert captured["resume_data"]["summary"] == long_text.strip()
    assert captured["resume_data"]["experience"][0]["raw_input"] == long_text.strip()


def test_pdf_export_rejects_unknown_template(client, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]

    response = client.post(
        f"/api/resume/{created['id']}/export",
        json={"template_choice": "experimental", "user_id": "test-user"},
    )

    assert response.status_code == 400
    assert "template_choice" in response.get_json()["message"]


def test_pdf_export_normalizes_legacy_template_aliases(client, monkeypatch, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]
    captured = {}

    def fake_render_resume_pdf(resume_data, template_choice):
        captured["template_choice"] = template_choice
        return b"%PDF-1.4\n% test pdf bytes\n"

    monkeypatch.setattr(
        "app.routes.resumes.render_resume_pdf",
        fake_render_resume_pdf,
    )

    response = client.post(
        f"/api/resumes/{created['id']}/download",
        json={"template_choice": "default", "user_id": "test-user"},
    )

    assert response.status_code == 200
    assert captured["template_choice"] == "steady-form"


def test_pdf_html_uses_selected_template_class(sample_resume_payload):
    html = pdf_export.render_resume_html(sample_resume_payload, "steady-form")

    assert 'class="resume-page template-steady-form layout-single-column"' in html


def test_preview_and_pdf_share_template_alignment_specs(sample_resume_payload):
    from app.template_catalog import TEMPLATE_CATALOG

    for template_id, *_rest in TEMPLATE_CATALOG:
        spec = pdf_export.template_style_spec(template_id)
        profile = pdf_export.reportlab_template_profile(template_id)
        html = pdf_export.render_resume_html(sample_resume_payload, template_id)

        assert f"--resume-header-align: {spec['header_alignment']}" in html
        assert f"--resume-section-align: {spec['section_alignment']}" in html
        assert profile["header_alignment"] == (1 if spec["header_alignment"] == "center" else 0)
        assert profile["section_alignment"] == (1 if spec["section_alignment"] == "center" else 0)
    assert "Demo User" in html


def test_all_catalog_templates_export_pdf(client, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]

    from app.template_catalog import TEMPLATE_CATALOG

    for template_id, *_rest in TEMPLATE_CATALOG:
        response = client.post(
            f"/api/resumes/{created['id']}/download",
            json={"template_choice": template_id, "user_id": "test-user"},
        )

        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF")


def test_every_catalog_template_renders_valid_pdf_bytes(sample_resume_payload):
    from app.template_catalog import TEMPLATE_CATALOG

    for template_id, *_rest in TEMPLATE_CATALOG:
        pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, template_id)

        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000


def test_catalog_templates_handle_long_content_without_placeholder_or_empty_section_leaks():
    from app.template_catalog import TEMPLATE_CATALOG

    payload = comprehensive_resume_payload()
    for template_id, *_rest in TEMPLATE_CATALOG:
        pdf_bytes = pdf_export.render_resume_pdf(payload, template_id)
        reader = PdfReader(BytesIO(pdf_bytes))
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)

        assert 1 <= len(reader.pages) <= 6, template_id
        assert "Alexandra Morgan-Smith" in extracted, template_id
        assert "Northstar Systems 1" in extracted, template_id
        assert "Operations Visibility Platform 1" in extracted, template_id
        assert "Python" in extracted, template_id
        assert "Cloud Practitioner" in extracted, template_id
        assert "Imported Company" not in extracted, template_id
        assert "Imported Project" not in extracted, template_id
        assert "PUBLICATIONS" not in extracted.upper(), template_id


def test_four_primary_templates_keep_selectable_header_order(sample_resume_payload):
    sample_resume_payload["target_role"] = "Data Analyst"

    for template_id in [
        "steady-form",
        "classic-serif",
        "mercury-flow",
        "slate-dawn",
    ]:
        pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, template_id)
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(BytesIO(pdf_bytes)).pages
        )

        assert text.index("Demo User") < text.index("Data Analyst")
        assert "TECHNICAL SKILLS" in text
        assert "Python" in text
        assert "React" in text


def test_primary_template_pdf_profile_links_are_clickable(sample_resume_payload):
    sample_resume_payload["personal_info"]["links"] = [
        "GitHub: github.com/demo-user",
        "LinkedIn: https://linkedin.com/in/demo-user",
        "Portfolio: example.com/portfolio",
    ]

    pdf_bytes = pdf_export.render_resume_pdf(sample_resume_payload, "steady-form")
    reader = PdfReader(BytesIO(pdf_bytes))
    uris = []

    for page in reader.pages:
        for annotation in page.get("/Annots") or []:
            action = annotation.get_object().get("/A") or {}
            uri = action.get("/URI")
            if uri:
                uris.append(uri)

    assert "https://github.com/demo-user" in uris
    assert "https://linkedin.com/in/demo-user" in uris
    assert "https://example.com/portfolio" in uris


def test_pdf_export_strips_bracketed_placeholders(client, sample_resume_payload):
    sample_resume_payload["personal_info"]["links"] = ["[Add GitHub URL]"]
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]

    response = client.post(
        f"/api/resumes/{created['id']}/download",
        json={"template_choice": "steady-form", "user_id": "test-user"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_plural_pdf_download_response_headers(client, monkeypatch, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]

    monkeypatch.setattr(
        "app.routes.resumes.render_resume_pdf",
        lambda resume_data, template_choice: b"%PDF-1.4\n% test pdf bytes\n",
    )

    response = client.post(
        f"/api/resumes/{created['id']}/download",
        json={"template_choice": "modern", "user_id": "test-user"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-1.4")
    assert "Demo_User_Software_Engineer_Resume" in response.headers["Content-Disposition"]


def test_live_preview_uses_pdf_renderer_and_inline_headers(client, monkeypatch, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]
    captured = {}

    def fake_render(resume_data, template_choice):
        captured["template_choice"] = template_choice
        return b"%PDF-1.4\n% exact preview\n"

    monkeypatch.setattr("app.routes.resumes.render_resume_pdf", fake_render)
    response = client.post(
        "/api/resumes/preview",
        headers={"X-User-Id": "test-user"},
        json={"resume": created, "template_choice": "slate-dawn", "user_id": "test-user"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-1.4")
    assert response.headers["Content-Disposition"].startswith("inline")
    assert captured["template_choice"] == "slate-dawn"
