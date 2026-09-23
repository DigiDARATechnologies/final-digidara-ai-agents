from io import BytesIO
import json
import zipfile

import pytest

from app.services import import_review
from app.services.import_review import ImportValidationError, analyze_resume_text, job_match
from app.routes import ai


def test_extract_professional_links_keeps_bare_profile_domains_without_fetching_them():
    links = import_review.extract_professional_links(
        "LinkedIn linkedin.com/in/alex GitHub github.com/alex Portfolio alex-portfolio.onrender.com"
    )

    assert links == {
        "linkedin": "linkedin.com/in/alex",
        "github": "github.com/alex",
        "portfolio": "alex-portfolio.onrender.com",
    }


COMPLETE_RESUME = """Alex Morgan
DATA ANALYST
alex@example.com | +91 98765 43210 | Chennai, India
LinkedIn: https://linkedin.com/in/alexmorgan
GitHub: https://github.com/alexmorgan

Profile
Data analyst with experience building dashboards, SQL reports, and Python data workflows for business teams.

Academic Background
Example University
Master of Computer Applications
2024 - 2026
CGPA: 8.7

Core Skills
Python, SQL, Power BI, Excel, Tableau, Data Cleaning, KPI Reporting, Pandas

Employment
Data Analyst Intern - Example Analytics
2025 - Present
- Built 12 KPI reports for operations stakeholders.
- Improved weekly reporting time by 30%.

Personal Projects
Sales Analytics Dashboard
Technologies: Power BI, SQL
Created dashboard for revenue, region, and category analysis.

Certificates and Licenses
Google Data Analytics Certificate
2025

Languages
English, Tamil
"""


def upload(client, content, filename="resume.txt", mimetype="text/plain", job_description="", target_role=""):
    data = {"file": (BytesIO(content), filename, mimetype)}
    if job_description:
        data["job_description"] = job_description
    if target_role:
        data["target_role"] = target_role
    return client.post(
        "/api/import-resume/analyze",
        data=data,
        content_type="multipart/form-data",
    )


def make_pdf(text=COMPLETE_RESUME):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for line in text.splitlines():
        pdf.drawString(54, y, line[:110])
        y -= 14
        if y < 54:
            pdf.showPage()
            y = 800
    pdf.save()
    return buffer.getvalue()


def make_docx(text=COMPLETE_RESUME):
    body = "".join(
        f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>"
        for line in text.splitlines()
        if line
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def test_valid_txt_upload_returns_parsed_resume_and_score(client):
    response = upload(client, COMPLETE_RESUME.encode("utf-8"))

    assert response.status_code == 200
    payload = response.get_json()["data"]
    parsed = payload["parsedResume"]
    assert payload["originalFileName"] == "resume.txt"
    assert payload["atsAnalysis"]["score"]["normalized_score"] >= 60
    assert payload["atsAnalysis"]["rating"] in {"Moderate Match", "Strong Match", "Excellent Match"}
    assert parsed["personalInfo"]["fullName"] == "Alex Morgan"
    assert parsed["personalInfo"]["email"] == "alex@example.com"
    assert parsed["education"]
    assert parsed["experience"]
    assert parsed["projects"]


def test_import_target_role_is_used_without_a_job_description(client):
    no_target = upload(client, COMPLETE_RESUME.encode("utf-8"))
    target_only = upload(client, COMPLETE_RESUME.encode("utf-8"), target_role="AI Engineer")

    assert no_target.status_code == 200
    assert target_only.status_code == 200
    assert no_target.get_json()["data"]["atsAnalysis"]["analysis_type"] == "resume_quality"
    assert target_only.get_json()["data"]["atsAnalysis"]["analysis_type"] == "job_match"


def test_import_parser_keeps_labeled_name_and_degree_before_institution():
    parsed, _ = import_review.parse_resume_text(
        """Name: Swetha S | Data Analyst
swetha@example.com

Education
Bachelor of Engineering in Computer Science
Example Institute of Technology
2021 - 2025
"""
    )

    assert parsed["personalInfo"]["fullName"] == "Swetha S"
    assert parsed["education"] == [
        {
            "school": "Example Institute of Technology",
            "degree": "Bachelor of Engineering in Computer Science",
            "field": "",
            "start_date": "2021",
            "end_date": "2025",
            "cgpa": "",
        }
    ]


def test_import_parser_recovers_single_word_name_and_project_evidence_from_publication():
    parsed, _ = import_review.parse_resume_text(
        """SwethaRubeshkanna
web developer
swetha@example.com | 6382 370 450

Education
Trichengode
2025
Master Of Computer Applications
K.S.R. College Of Engineering
2023
Bachelor Of Computer Applications
K.S.R. College For Womens

Publications
January 2025 Efficient AI-Driven Health Monitoring Facial Recognition in Cattle Farms
January 2025
Built an AI system that identifies cattle using facial recognition and monitors their health in real time.

Declaration
I hereby declare that the above-mentioned information is true.
Swetha S
"""
    )

    assert parsed["personalInfo"]["fullName"] == "SwethaRubeshkanna"
    assert parsed["targetRole"] == "web developer"
    assert [entry["school"] for entry in parsed["education"]] == [
        "K.S.R. College Of Engineering",
        "K.S.R. College For Womens",
    ]
    assert parsed["projects"] == [{
        "title": "Efficient AI-Driven Health Monitoring Facial Recognition in Cattle Farms",
        "description": "Built an AI system that identifies cattle using facial recognition and monitors their health in real time.",
    }]
    assert parsed["declaration"].endswith("Swetha S")


def test_import_parser_keeps_one_project_with_multiple_details_as_one_record():
    parsed, _ = import_review.parse_resume_text(
        """Alex Morgan
Data Analyst
alex@example.com

Projects
Customer Retention Analytics Platform
Technologies: Python, SQL, Power BI
- Built a churn dashboard for weekly leadership reviews.
- Combined customer events and billing records into a reusable data model.
"""
    )

    assert parsed["projects"] == [{
        "title": "Customer Retention Analytics Platform",
        "description": "Technologies: Python, SQL, Power BI\n- Built a churn dashboard for weekly leadership reviews.\n- Combined customer events and billing records into a reusable data model.",
    }]


def test_import_parser_preserves_every_publication_with_its_own_details():
    parsed, _ = import_review.parse_resume_text(
        """Alex Morgan
Data Analyst
alex@example.com

Publications
Data Quality in Operational Analytics
January 2024
Published a reproducible dashboard quality framework.
Forecasting Demand with Transparent Models
February 2025
Presented a practical demand forecasting evaluation.
"""
    )

    assert [item["title"] for item in parsed["publications"]] == [
        "Data Quality in Operational Analytics",
        "Forecasting Demand with Transparent Models",
    ]


@pytest.mark.parametrize(
    ("score_line", "expected_score"),
    [
        ("CGPA: 8.5", "8.5"),
        ("CGPA: 8.5/10", "8.5/10"),
        ("Percentage: 85%", "Percentage: 85%"),
        ("CGPA: 8.5/10 | Percentage: 85%", "8.5/10 | Percentage: 85%"),
    ],
)
def test_import_parser_preserves_cgpa_and_percentage(score_line, expected_score):
    parsed, _ = import_review.parse_resume_text(
        f"""Alex Morgan
Data Analyst
alex@example.com

Education
Example University
Master of Computer Applications
2024 - 2026
{score_line}
"""
    )

    assert parsed["education"][0]["cgpa"] == expected_score


def test_import_parser_keeps_role_dates_and_bullets_in_one_experience_record():
    parsed, _ = import_review.parse_resume_text(
        """Alex Morgan
Data Analyst
alex@example.com

Experience
Data Analyst - Northstar Systems
January 2024 - Present
- Built a governed reporting dataset for operations leaders.
- Reduced weekly manual reporting through automated quality checks.
"""
    )

    assert len(parsed["experience"]) == 1
    experience = parsed["experience"][0]
    assert experience["company"] == "Northstar Systems"
    assert experience["role"] == "Data Analyst"
    assert experience["ai_generated_bullets"] == [
        "Built a governed reporting dataset for operations leaders.",
        "Reduced weekly manual reporting through automated quality checks.",
    ]


def test_import_parser_preserves_present_as_explicit_current_role_state():
    parsed, _ = import_review.parse_resume_text(
        """Alex Morgan
Data Analyst
alex@example.com

Experience
Data Analyst - Northstar Systems
January 2024 - Present
- Built reporting datasets.
"""
    )

    assert parsed["experience"][0]["is_current"] is True


def test_import_parser_separates_real_project_and_experience_entries():
    parsed, _ = import_review.parse_resume_text(
        """Alex Morgan
Data Analyst
alex@example.com

Experience
Data Analyst - Northstar Systems
January 2024 - December 2024
- Built reporting datasets.
Analytics Engineer - Orbit Labs
January 2025 - Present
- Built reliable transformation pipelines.

Projects
Customer Retention Platform
Technologies: Python, SQL
- Built churn reporting.
Operational Forecasting Tool
Technologies: Python, Power BI
- Built forecast scenarios.
"""
    )

    assert [item["company"] for item in parsed["experience"]] == ["Northstar Systems", "Orbit Labs"]
    assert [item["title"] for item in parsed["projects"]] == ["Customer Retention Platform", "Operational Forecasting Tool"]


def test_import_payload_merges_only_obvious_legacy_project_and_experience_fragments():
    payload = import_review.map_import_to_resume_payload(
        {
            "personalInfo": {},
            "projects": [
                {"title": "Social Media Insights Dashboard", "description": "Built dashboard visuals."},
                {"title": "supporting data-driven decision-making.", "description": ""},
                {"title": "Forecasting Tool", "description": "A separate project."},
            ],
            "experience": [
                {"company": "Example Co", "role": "Data Analyst", "ai_generated_bullets": ["Built reports."]},
                {"company": "Imported Company", "role": "January 2024 - Present", "ai_generated_bullets": ["Improved reporting."]},
            ],
        },
        "resume.pdf",
        "test-user",
    )

    assert [project["title"] for project in payload["projects"]] == ["Social Media Insights Dashboard", "Forecasting Tool"]
    assert payload["projects"][0]["description"].endswith("supporting data-driven decision-making.")
    assert len(payload["experience"]) == 1
    assert payload["experience"][0]["ai_generated_bullets"] == ["Built reports.", "Improved reporting."]


def test_import_payload_never_inserts_candidate_or_education_placeholders():
    payload = import_review.map_import_to_resume_payload(
        {"personalInfo": {}, "education": [{"degree": "BSc"}]},
        "resume.pdf",
        "test-user",
    )

    assert payload["personal_info"]["name"] == ""
    assert payload["personal_info"]["email"] == ""
    assert payload["education"][0]["school"] == ""


def test_import_analysis_warns_when_name_or_education_cannot_be_extracted():
    parsed, _ = import_review.parse_resume_text("missing@example.com\n+91 98765 43210")
    problems = {
        item["problem"]
        for item in import_review.build_critical_issues(parsed, "", [])
    }

    assert "Missing full name" in problems
    assert "Missing education details" in problems


def test_valid_pdf_upload_extracts_text(client):
    response = upload(client, make_pdf(), filename="resume.pdf", mimetype="application/pdf")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["file"]["type"] == "pdf"
    assert payload["file"]["pageCount"] >= 1
    assert payload["parsedResume"]["personalInfo"]["fullName"] == "Alex Morgan"


def test_valid_docx_upload_extracts_text(client):
    response = upload(
        client,
        make_docx(),
        filename="resume.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["file"]["type"] == "docx"
    assert payload["parsedResume"]["skills"]


def test_legacy_doc_without_converter_returns_specific_error(client):
    response = upload(
        client,
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"legacy-doc",
        filename="resume.doc",
        mimetype="application/msword",
    )

    assert response.status_code in {400, 422}
    assert "legacy Word document" in response.get_json()["message"]


def test_upload_rejects_unsupported_extension(client):
    response = upload(client, b"Alex Morgan", filename="resume.exe", mimetype="application/octet-stream")

    assert response.status_code == 415
    assert "Unsupported format" in response.get_json()["message"]


def test_upload_rejects_extension_mime_mismatch(client):
    response = upload(client, COMPLETE_RESUME.encode("utf-8"), filename="resume.pdf", mimetype="text/plain")

    assert response.status_code == 415
    assert "MIME" in response.get_json()["message"]


def test_upload_rejects_oversized_file(client):
    response = upload(client, b"a" * (5 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert "5 MB" in response.get_json()["message"]


def test_upload_rejects_empty_file(client):
    response = upload(client, b"")

    assert response.status_code == 400
    assert "empty" in response.get_json()["message"].lower()


def test_upload_rejects_invalid_utf8(client):
    response = upload(client, b"\xff\xfe\x00\x00")

    assert response.status_code == 400
    assert "UTF-8" in response.get_json()["message"]


def test_corrupted_pdf_is_rejected(client):
    response = upload(client, b"%PDF corrupted", filename="resume.pdf", mimetype="application/pdf")

    assert response.status_code == 400
    assert "PDF" in response.get_json()["message"]


def test_image_only_pdf_is_rejected(client):
    response = upload(client, make_pdf("Only words"), filename="resume.pdf", mimetype="application/pdf")

    assert response.status_code == 422
    assert "selectable text" in response.get_json()["message"]


def test_ocr_pdf_pages_extracts_text_from_rendered_pdf():
    raw = make_pdf(COMPLETE_RESUME)

    text = import_review.ocr_pdf_pages(raw)

    assert text is not None
    assert "Alex Morgan" in text or "DATA ANALYST" in text.upper()


def test_image_only_pdf_falls_back_to_ocr(client, monkeypatch):
    from pypdf._page import PageObject

    # Simulate a real scanned PDF: the selectable text layer is empty even though
    # the page content can still be rasterized and OCR'd.
    monkeypatch.setattr(PageObject, "extract_text", lambda self, *a, **k: "")

    response = upload(client, make_pdf(COMPLETE_RESUME), filename="resume.pdf", mimetype="application/pdf")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert "Alex Morgan" in payload["extractedText"] or "DATA ANALYST" in payload["extractedText"].upper()
    assert any("OCR" in warning for warning in payload.get("extractionWarnings", []))


def test_ocr_upload_content_reaches_whole_resume_llm(client, monkeypatch):
    """Prove OCR text flows through import parsing into optimize-resume prompts."""
    from pypdf._page import PageObject

    monkeypatch.setattr(PageObject, "extract_text", lambda self, *args, **kwargs: "")
    prompts = []

    def fake_ai_response(prompt, max_tokens):
        prompts.append(prompt)
        assert "complete, truthful resume optimization" in prompt
        return json.dumps({
            "summary": "OCR-generated data analyst summary.",
            "skills": [],
            "experience": [
                {"index": index, "bullets": ["OCR-derived resume bullet."]}
                for index, item in enumerate(parsed_resume["experience"])
                if item.get("raw_input")
            ],
            "projects": [
                {"index": index, "bullets": ["OCR-derived resume bullet."]}
                for index, item in enumerate(parsed_resume["projects"])
                if item.get("description")
            ],
        })

    monkeypatch.setattr(ai, "get_ai_response_text", fake_ai_response)
    analyzed = upload(client, make_pdf(COMPLETE_RESUME), filename="scanned-resume.pdf", mimetype="application/pdf")

    assert analyzed.status_code == 200
    parsed_resume = analyzed.get_json()["data"]["parsedResume"]
    assert parsed_resume["experience"]
    assert parsed_resume["projects"]
    assert any(item.get("raw_input") for item in parsed_resume["experience"])
    assert any(item.get("description") for item in parsed_resume["projects"])

    optimized = client.post(
        "/api/ai/optimize-resume",
        json={"resume": parsed_resume, "target_role": "Data Analyst"},
    )

    assert optimized.status_code == 200
    assert any("KPI reports" in prompt or "operations stakeholders" in prompt for prompt in prompts)
    assert any("revenue, region, and category analysis" in prompt for prompt in prompts)
    assert optimized.get_json()["resume"]["summary"] == "OCR-generated data analyst summary."


def test_corrupted_docx_is_rejected(client):
    response = upload(client, b"PKbadzip", filename="resume.docx", mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert response.status_code == 400
    assert "DOCX" in response.get_json()["message"]


def test_docx_with_xml_entity_expansion_is_rejected_cleanly(client):
    malicious_document = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
]>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>&lol2;</w:t></w:r></w:p></w:body>
</w:document>
"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", malicious_document)

    response = upload(
        client,
        buffer.getvalue(),
        filename="resume.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert response.status_code == 400
    assert "DOCX" in response.get_json()["message"]


def test_legacy_job_match_uses_resume_values_and_normalizes_word_variants():
    parsed = {
        "personalInfo": {"fullName": "Alex", "location": ""},
        "summary": "Managed product launches and customer communication.",
        "skills": [{"skill_name": "Planning"}],
        "experience": [],
    }

    result = job_match(parsed, "Location managing planning leadership")

    assert result["matchedKeywords"] == ["managing", "planning"]
    assert "location" in result["missingKeywords"]


def test_docx_decompression_limit_does_not_trust_zipinfo_file_size(monkeypatch):
    class FakeInfo:
        def __init__(self, filename, file_size):
            self.filename = filename
            self.file_size = file_size

    class FakeMember:
        def __init__(self, chunks):
            self.chunks = list(chunks)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size=-1):
            return self.chunks.pop(0) if self.chunks else b""

    class FakeZipFile:
        def __init__(self, _raw):
            self._infos = [
                FakeInfo("[Content_Types].xml", 1),
                FakeInfo("word/document.xml", 1),
            ]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def infolist(self):
            return self._infos

        def open(self, info):
            if info.filename == "[Content_Types].xml":
                return FakeMember([b"<Types/>"])
            return FakeMember([b"a" * 16, b"b" * 16])

    monkeypatch.setattr(import_review.zipfile, "ZipFile", FakeZipFile)
    monkeypatch.setattr(import_review, "MAX_DOCX_UNCOMPRESSED_BYTES", 24)

    with pytest.raises(ImportValidationError, match="too large after decompression"):
        import_review.extract_docx("resume.docx", b"PKfake")


def test_legacy_doc_conversion_uses_isolated_libreoffice_profile(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, cwd, **_kwargs):
        captured["command"] = command
        profile_arg = next(item for item in command if item.startswith("-env:UserInstallation="))
        profile_uri = profile_arg.split("=", 1)[1]
        assert profile_uri.startswith("file:///")
        from urllib.parse import urlsplit
        from urllib.request import url2pathname
        profile_path = import_review.Path(url2pathname(urlsplit(profile_uri).path))
        registry = profile_path / "user" / "registrymodifications.xcu"
        assert registry.exists()
        assert "MacroSecurityLevel" in registry.read_text(encoding="utf-8")
        import_review.Path(cwd, "resume.txt").write_text("Converted resume text", encoding="utf-8")

    converter = tmp_path / "soffice"
    converter.write_text("trusted test binary", encoding="utf-8")
    monkeypatch.setenv("LIBREOFFICE_BINARY", str(converter))
    monkeypatch.setattr(import_review.subprocess, "run", fake_run)

    result = import_review.extract_doc(
        "resume.doc",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-doc",
    )

    assert result["fileType"] == "doc"
    assert "--headless" in captured["command"]
    assert "--norestore" in captured["command"]
    assert any(item.startswith("-env:UserInstallation=") for item in captured["command"])


def test_section_heading_variations_are_detected():
    result = analyze_resume_text(COMPLETE_RESUME, filename="resume.txt")

    parsed = result["parsedResume"]
    assert parsed["summary"]
    assert parsed["education"]
    assert parsed["skills"]
    assert parsed["experience"]
    assert parsed["certifications"]


def test_score_is_deterministic():
    first = analyze_resume_text(COMPLETE_RESUME, filename="resume.txt")
    second = analyze_resume_text(COMPLETE_RESUME, filename="resume.txt")

    assert first["atsAnalysis"]["score"] == second["atsAnalysis"]["score"]
    assert first["atsAnalysis"]["categories"] == second["atsAnalysis"]["categories"]


def test_unmapped_content_is_preserved():
    result = analyze_resume_text(COMPLETE_RESUME + "\nAwards\nWon college hackathon\n", filename="resume.txt")

    assert "Won college hackathon" in result["unmappedContent"]
    assert result["atsAnalysis"]["formatting_warnings"]


def test_missing_contact_information_creates_critical_issues():
    result = analyze_resume_text("Alex Morgan\nSkills\nPython, SQL", filename="resume.txt")

    assert result["atsAnalysis"]["score"]["normalized_score"] < 50
    assert result["atsAnalysis"]["breakdown"]["contact_quality"]["earned"] < 3


def test_import_draft_creates_editable_resume(client):
    analysis = analyze_resume_text(COMPLETE_RESUME, filename="resume.txt")
    response = client.post(
        "/api/import-resume/draft",
        json={
            "user_id": "test-user",
            "originalFileName": "resume.txt",
            "parsedResume": analysis["parsedResume"],
        },
    )

    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["id"]
    assert payload["target_role"] == "DATA ANALYST"
    assert payload["personal_info"]["name"] == "Alex Morgan"
    assert payload["skills"]
    assert payload["experience"]
