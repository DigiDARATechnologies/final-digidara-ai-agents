"""Integration tests for the production repository, never the mock repository."""
import os
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit

import pytest
from lms_api import create_app
from lms_api.errors import ApiError
from lms_api.repository import MySqlRepository

@pytest.fixture(scope="module")
def repository():
    value = os.environ.get("INTEGRATION_DATABASE_URL")
    if not value:
        pytest.skip("Run through scripts/test_agents.py for isolated MySQL integration")
    url = urlsplit(value)
    database = url.path.lstrip("/")
    if url.scheme != "mysql+pymysql" or not database.endswith("_test"):
        raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
    # Migration and repository must target precisely the guarded database.
    if os.environ.get("MYSQL_DATABASE") != database or os.environ.get("MYSQL_HOST") != url.hostname:
        raise RuntimeError("Migration database does not match the integration test URL")
    subprocess.run([sys.executable, "scripts/migrate.py", "up"], check=True)
    app = create_app({"TESTING": True})
    with app.app_context():
        yield MySqlRepository()

def test_registration_login_and_session_revocation(repository):
    email = f"integration-{uuid.uuid4().hex}@example.test"
    student, token, _ = repository.register_account(email, "Strong-password-123!", "Integration learner")
    assert repository.student_for_session(token)["id"] == student["id"]
    logged_in, new_token, _ = repository.login_account(email, "Strong-password-123!")
    assert logged_in["id"] == student["id"]
    repository.revoke_session(new_token)
    assert repository.student_for_session(new_token) is None
    assert repository.student_for_session(token)["id"] == student["id"]
    with pytest.raises(ApiError):
        repository.login_account(email, "wrong-password")
    with pytest.raises(ApiError):
        repository.register_account(email, "Strong-password-123!", "Duplicate")

def test_request_nonce_is_persisted_across_repository_instances(repository):
    request_id = uuid.uuid4().hex
    assert repository.claim_request(request_id, int(time.time())) is True
    assert MySqlRepository().claim_request(request_id, int(time.time())) is False
