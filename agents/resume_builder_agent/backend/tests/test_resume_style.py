"""Candidate-chosen font family, text size and line spacing (app/services/resume_style.py)."""
import json

import pytest

from app.routes import ai
from app.services import pdf_export, resume_style
from app.template_catalog import VALID_TEMPLATE_IDS


def test_style_is_validated_and_defaults_to_the_template():
    assert resume_style.normalize_style(None) == resume_style.DEFAULT_STYLE
    assert resume_style.normalize_style({"font_family": "lato", "font_scale": 1.07, "line_spacing": "1.2"}) == {
        "font_family": "lato", "font_scale": 1.05, "line_spacing": 1.15,
    }
    assert resume_style.normalize_style({"font_family": "comic-sans"})["font_family"] == "template"
    with pytest.raises(ValueError):
        resume_style.normalize_style({"font_family": "comic-sans"}, strict=True)
    with pytest.raises(ValueError):
        resume_style.normalize_style({"font_scale": "big"}, strict=True)


def test_the_default_style_leaves_paragraph_style_untouched():
    from reportlab.lib.styles import ParagraphStyle
    assert resume_style.styled_paragraph_style(ParagraphStyle, None) is ParagraphStyle
    assert resume_style.styled_paragraph_style(ParagraphStyle, resume_style.DEFAULT_STYLE) is ParagraphStyle


def test_font_and_size_are_applied_once_through_inheritance():
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    Styled = resume_style.styled_paragraph_style(ParagraphStyle, {"font_family": "carlito", "font_scale": 1.2, "line_spacing": 1.15})
    normal = getSampleStyleSheet()["Normal"]  # 10pt, leading 12
    body = Styled("Body", parent=normal)
    assert body.fontName == "Carlito"
    assert body.fontSize == 12.0 and body.leading == round(12 * 1.2 * 1.15, 2)
    heading = Styled("Heading", parent=body, fontName="Helvetica-Bold", fontSize=20)
    assert heading.fontName == "Carlito-Bold"
    assert heading.fontSize == 24.0
    child = Styled("Child", parent=heading)  # inherits an already-scaled size
    assert child.fontSize == 24.0 and child.fontName == "Carlito-Bold"
    italic = Styled("Italic", parent=normal, fontName="Times-BoldItalic")
    assert italic.fontName == "Carlito-BoldItalic"


@pytest.mark.parametrize("family", [key for key in resume_style.FONT_FAMILIES if key != "template"])
def test_every_font_renders_every_template(sample_resume_payload, family):
    style = {"font_family": family, "font_scale": 1.1, "line_spacing": 1.15}
    embedded = {"carlito": b"Carlito", "lato": b"Lato", "open-sans": b"OpenSans", "liberation-serif": b"LiberationSerif",
                "helvetica": b"Helvetica", "times": b"Times"}[family]
    for template in sorted(VALID_TEMPLATE_IDS):
        pdf = pdf_export.render_resume_pdf(sample_resume_payload, template, style)
        assert pdf.startswith(b"%PDF"), template
        assert embedded in pdf, (family, template)


def test_template_default_keeps_the_template_fonts(sample_resume_payload):
    pdf = pdf_export.render_resume_pdf(sample_resume_payload, "steady-form", resume_style.DEFAULT_STYLE)
    for bundled in (b"Carlito", b"Lato", b"OpenSans", b"LiberationSerif"):
        assert bundled not in pdf


def test_style_options_are_listed(client):
    body = client.get("/api/resume-styles").get_json()
    assert [family["id"] for family in body["font_families"]][:2] == ["template", "carlito"]
    assert body["default"] == resume_style.DEFAULT_STYLE


def test_a_saved_style_is_used_for_the_download(client, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]
    headers = {"X-User-Id": "test-user"}
    saved = client.put(f"/api/resumes/{created['id']}", json={"user_id": "test-user", "style_settings": {"font_family": "open-sans", "font_scale": 1.1, "line_spacing": 1.0}}, headers=headers)
    assert saved.status_code == 200, saved.get_json()
    fetched = client.get(f"/api/resumes/{created['id']}", headers=headers).get_json()["data"]
    assert fetched["style_settings"] == {"font_family": "open-sans", "font_scale": 1.1, "line_spacing": 1.0}
    pdf = client.post(f"/api/resumes/{created['id']}/download", json={"user_id": "test-user"}, headers=headers)
    assert pdf.status_code == 200
    assert b"OpenSans" in pdf.data


def test_an_unknown_font_is_refused(client, sample_resume_payload):
    created = client.post("/api/resume", json=sample_resume_payload).get_json()["data"]
    response = client.put(f"/api/resumes/{created['id']}", json={"user_id": "test-user", "style_settings": {"font_family": "papyrus"}}, headers={"X-User-Id": "test-user"})
    assert response.status_code == 400


def test_the_preview_uses_the_style_it_is_given(client, sample_resume_payload):
    response = client.post("/api/resumes/preview", json={
        "user_id": "test-user", "resume": sample_resume_payload, "template_choice": "steady-form",
        "style_settings": {"font_family": "liberation-serif"},
    }, headers={"X-User-Id": "test-user"})
    assert response.status_code == 200
    assert b"LiberationSerif" in response.data


def test_ai_style_suggestion_is_limited_to_the_offered_options(client, monkeypatch):
    monkeypatch.setattr(ai, "get_ai_response_text", lambda prompt, max_tokens: json.dumps(
        {"font_family": "lato", "font_scale": 0.97, "line_spacing": 1.0, "reason": "Lato is clean and modern."}))
    body = client.post("/api/ai/suggest-resume-style", json={"resume": {"target_role": "Data Analyst", "experience_level": "fresher"}}).get_json()
    assert body == {"style": {"font_family": "lato", "font_scale": 0.95, "line_spacing": 1.0}, "reason": "Lato is clean and modern.", "source": "ai"}


@pytest.mark.parametrize("model_answer", [RuntimeError("AI provider is not configured"), {"font_family": "Comic Sans"}])
def test_without_a_usable_ai_answer_a_rule_based_style_is_suggested(client, monkeypatch, model_answer):
    def respond(prompt, max_tokens):
        if isinstance(model_answer, Exception):
            raise model_answer
        return json.dumps(model_answer)
    monkeypatch.setattr(ai, "get_ai_response_text", respond)
    body = client.post("/api/ai/suggest-resume-style", json={"resume": {"target_role": "Chartered Accountant", "experience_level": "experienced"}}).get_json()
    assert body["source"] == "rules"
    assert body["style"]["font_family"] == "liberation-serif"
    assert body["reason"]


def test_the_suggestion_is_reachable_through_invoke(client, monkeypatch):
    monkeypatch.setattr(ai, "get_ai_response_text", lambda prompt, max_tokens: json.dumps({"font_family": "carlito", "font_scale": 1.0, "line_spacing": 1.0, "reason": "Clean."}))
    response = client.post("/api/invoke", json={"action": "suggest_resume_style", "payload": {"user_id": "test-user", "resume": {}}})
    assert response.status_code == 200
    assert response.get_json()["style"]["font_family"] == "carlito"
