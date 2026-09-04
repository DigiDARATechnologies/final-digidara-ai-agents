from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dependency_audit_workflow_runs_backend_and_frontend_scans():
    workflow = (REPO_ROOT / ".github" / "workflows" / "security-audit.yml").read_text(encoding="utf-8")

    assert "pip-audit -r backend/requirements.txt" in workflow
    assert "npm audit --production --audit-level=high" in workflow


def test_security_audit_records_current_dependency_findings_as_fixed():
    audit = (REPO_ROOT / "SECURITY_AUDIT.md").read_text(encoding="utf-8")

    assert "current backend findings were fixed" in audit
    assert "Flask, flask-cors, cryptography, pypdf, python-dotenv, and pytest" in audit
    assert "frontend audit reports 0 vulnerabilities" in audit
