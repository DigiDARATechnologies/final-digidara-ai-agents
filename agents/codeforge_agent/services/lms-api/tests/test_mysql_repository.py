"""Integration tests for the production repository, never the mock repository."""
import json
import os
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit

import pytest
from lms_api import create_app
from lms_api.db import connection
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


def _make_mcq_problem(topic_id, options, correct_key, explanation="Because that's the rule.", max_score=100):
    """Inserts directly (repository has no admin-side "create problem" method
    -- that's scripts/seed.py's job) so these tests don't depend on the
    content catalog having been seeded."""
    slug = f"mcq-{uuid.uuid4().hex}"
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO coding_problems (topic_id,name,slug,description,input_format,output_format,constraints_text,"
            "examples_json,starter_code,language_key,judge0_language_id,question_type,mcq_options_json,mcq_correct_key,"
            "mcq_explanation,difficulty,max_score,display_order) "
            "VALUES (%s,%s,%s,%s,'','','','[]',NULL,'html',NULL,'mcq',%s,%s,%s,'Easy',%s,1)",
            (topic_id, "Integration MCQ", slug, "Which one is correct?", json.dumps(options), correct_key, explanation, max_score),
        )
        problem_id = cursor.lastrowid
        conn.commit()
    return problem_id, slug


@pytest.fixture(scope="module")
def mcq_topic(repository):
    del repository
    with connection() as conn, conn.cursor() as cursor:
        course_slug = f"mcq-course-{uuid.uuid4().hex}"
        cursor.execute(
            "INSERT INTO coding_courses (name,slug,description,icon_key,display_order) VALUES (%s,%s,'d','I',999)",
            (course_slug, course_slug),
        )
        course_id = cursor.lastrowid
        tech_slug = f"mcq-tech-{uuid.uuid4().hex}"
        cursor.execute(
            "INSERT INTO coding_technologies (name,slug,description,icon_key,display_order) VALUES (%s,%s,'d','I',999)",
            (tech_slug, tech_slug),
        )
        tech_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO course_technologies (course_id,technology_id,display_order) VALUES (%s,%s,1)",
            (course_id, tech_id),
        )
        topic_slug = f"mcq-topic-{uuid.uuid4().hex}"
        cursor.execute(
            "INSERT INTO coding_topics (technology_id,name,slug,description,learning_objectives,suggested_concepts,display_order) "
            "VALUES (%s,%s,%s,'d','[]','[]',1)",
            (tech_id, topic_slug, topic_slug),
        )
        topic_id = cursor.lastrowid
        conn.commit()
    return {"course_slug": course_slug, "technology_slug": tech_slug, "topic_id": topic_id}


def test_get_problem_for_an_mcq_returns_options_but_never_the_answer(repository, mcq_topic):
    _problem_id, slug = _make_mcq_problem(mcq_topic["topic_id"], {"A": "First", "B": "Second"}, "B")
    student, _token, _ = repository.register_account(f"mcq-{uuid.uuid4().hex}@example.test", "Strong-password-123!", "Learner")

    # get_problem resolves the topic through list_problems -> list_topics, so
    # it needs the real topic slug -- fetch it back from the id mcq_topic gave us.
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT slug FROM coding_topics WHERE id=%s", (mcq_topic["topic_id"],))
        topic_slug = cursor.fetchone()["slug"]
    _course, _technology, _topic, problem = repository.get_problem(
        student["id"], mcq_topic["course_slug"], mcq_topic["technology_slug"], topic_slug, slug
    )

    assert problem["question_type"] == "mcq"
    assert problem["options"] == {"A": "First", "B": "Second"}
    assert "mcq_correct_key" not in problem
    assert "correctKey" not in problem


def test_submit_mcq_answer_scores_correctly_and_reveals_the_answer(repository, mcq_topic):
    problem_id, _slug = _make_mcq_problem(mcq_topic["topic_id"], {"A": "First", "B": "Second"}, "B", explanation="B is right because...")
    student, _token, _ = repository.register_account(f"mcq-{uuid.uuid4().hex}@example.test", "Strong-password-123!", "Learner")

    wrong = repository.submit_mcq_answer(student["id"], problem_id, "A")
    assert wrong["isCorrect"] is False
    assert wrong["score"] == 0
    assert wrong["correctKey"] == "B"
    assert wrong["explanation"] == "B is right because..."

    right = repository.submit_mcq_answer(student["id"], problem_id, "B")
    assert right["isCorrect"] is True
    assert right["score"] == 100
    assert right["mode"] == "submit"


def test_submit_mcq_answer_rejects_an_unknown_option_key(repository, mcq_topic):
    problem_id, _slug = _make_mcq_problem(mcq_topic["topic_id"], {"A": "First", "B": "Second"}, "B")
    student, _token, _ = repository.register_account(f"mcq-{uuid.uuid4().hex}@example.test", "Strong-password-123!", "Learner")

    with pytest.raises(ApiError):
        repository.submit_mcq_answer(student["id"], problem_id, "Z")


def test_submit_mcq_answer_rejects_a_code_problem(repository, mcq_topic):
    with connection() as conn, conn.cursor() as cursor:
        slug = f"code-{uuid.uuid4().hex}"
        cursor.execute(
            "INSERT INTO coding_problems (topic_id,name,slug,description,input_format,output_format,constraints_text,"
            "examples_json,starter_code,language_key,judge0_language_id,difficulty,max_score,display_order) "
            "VALUES (%s,'Code One',%s,'d','d','d','d','[]','print()','python',71,'Easy',100,2)",
            (mcq_topic["topic_id"], slug),
        )
        problem_id = cursor.lastrowid
        conn.commit()
    student, _token, _ = repository.register_account(f"mcq-{uuid.uuid4().hex}@example.test", "Strong-password-123!", "Learner")

    with pytest.raises(ApiError):
        repository.submit_mcq_answer(student["id"], problem_id, "A")
