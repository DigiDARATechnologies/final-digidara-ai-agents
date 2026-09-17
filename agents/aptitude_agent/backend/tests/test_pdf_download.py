from io import BytesIO
import uuid

from pypdf import PdfReader
from datetime import datetime, timezone

from backend.app.extensions import db
from backend.app.models import AptitudeAnswer, AptitudeTest, AptitudeTestQuestion, Student
from backend.app.models.base import utcnow
from backend.app.utils.timezone import format_local_datetime, valid_timezone


def _completed_test(student_id):
    test_id=str(uuid.uuid4());question_id=str(uuid.uuid4())
    test=AptitudeTest(
        id=test_id,student_id=student_id,status="completed",current_sequence=1,
        total_questions=1,test_mode="category_practice",
        selected_category="Logical Reasoning",selected_level="Beginner",
        correct_count=1,score=1,percentage=100,total_time_seconds=18,
        completed_at=utcnow(),
    )
    question=AptitudeTestQuestion(
        id=question_id,test_id=test_id,sequence_no=1,
        category="Logical Reasoning",topic="Number Series",difficulty="Easy",
        question_text="What comes next in the sequence 2, 4, 6, 8?",
        option_a="9",option_b="10",option_c="11",option_d="12",
        correct_answer="B",explanation="The sequence increases by 2, so the answer is 10.",
        generation_model="test",content_hash=f"pdf-{question_id}",
    )
    answer=AptitudeAnswer(
        id=str(uuid.uuid4()),test_id=test_id,student_id=student_id,
        question_id=question_id,selected_answer="B",correct_answer="B",
        is_correct=True,timed_out=False,time_taken_seconds=18,
        evaluation_source="authoritative",
        confidence_rating=5,reasoning_text="DORMANT REASONING MUST NOT EXPORT",
        mistake_type="not_applicable",
        mistake_explanation="DORMANT DIAGNOSIS MUST NOT EXPORT",
        diagnostics_status="completed",
    )
    db.session.add_all([test,question,answer]);db.session.commit()
    return test_id


def _pdf_text(response):
    reader=PdfReader(BytesIO(response.data))
    assert len(reader.pages)>=1
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _completed_technical_test(student_id):
    test_id=str(uuid.uuid4());question_id=str(uuid.uuid4())
    test=AptitudeTest(
        id=test_id,student_id=student_id,status="completed",current_sequence=1,
        total_questions=1,test_mode="category_practice",
        selected_category="Technical Aptitude",selected_level="Beginner",
        technical_language="C",correct_count=1,score=1,percentage=100,
        total_time_seconds=12,completed_at=utcnow(),
    )
    question=AptitudeTestQuestion(
        id=question_id,test_id=test_id,sequence_no=1,category="Technical Aptitude",
        topic="Programming Fundamentals",difficulty="Easy",
        question_text=r'Consider this C program:\\n\\n#include <stdio.h>\\nint main() {\\n    printf("Hello");\\n    return 0;\\n}',
        option_a="Hello",option_b="Error",option_c="Nothing",option_d="0",
        correct_answer="A",explanation="The program prints Hello.",
        generation_model="test",content_hash=f"pdf-technical-{question_id}",
    )
    answer=AptitudeAnswer(
        id=str(uuid.uuid4()),test_id=test_id,student_id=student_id,
        question_id=question_id,selected_answer="A",correct_answer="A",
        is_correct=True,timed_out=False,time_taken_seconds=12,
        evaluation_source="authoritative",
    )
    db.session.add_all([test,question,answer]);db.session.commit()
    return test_id


def test_completed_test_pdf_has_expected_content_and_excludes_dormant_diagnostics(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=_completed_test(student.id)

    response=client.get(f"/api/aptitude/tests/{test_id}/download",headers=auth_headers)
    assert response.status_code==200
    assert response.mimetype=="application/pdf"
    assert f'test-results-' in response.headers["Content-Disposition"]
    assert test_id in response.headers["Content-Disposition"]
    assert response.data.startswith(b"%PDF-")

    text=_pdf_text(response)
    assert "Test Learner" in text
    assert "Category Practice" in text
    assert "Logical Reasoning" in text
    assert "Beginner" in text
    assert "100%" in text
    assert "What comes next in the sequence 2, 4, 6, 8?" in text
    assert "B.\n10" in text
    assert "Your answer: B" in text
    assert "Correct answer: B" in text
    assert "The sequence increases by 2, so the answer is 10." in text
    assert "DORMANT REASONING MUST NOT EXPORT" not in text
    assert "DORMANT DIAGNOSIS MUST NOT EXPORT" not in text
    assert "confidence" not in text.lower()
    assert "No priority topics identified for this assessment." in text
    assert "Aptitude Test" in text
    assert "AptiDARA" not in text


def test_pdf_uses_validated_student_timezone_and_safe_fallbacks():
    instant=datetime(2026,9,12,6,54,tzinfo=timezone.utc)
    assert format_local_datetime(instant,"Asia/Kolkata")=="12 Sep 2026, 12:24 PM IST"
    assert format_local_datetime(instant,"America/New_York")=="12 Sep 2026, 02:54 AM EDT"
    assert format_local_datetime(instant,"Europe/London")=="12 Sep 2026, 07:54 AM BST"
    assert valid_timezone("invalid/timezone") is None
    assert valid_timezone("Asia/Calcutta")=="Asia/Kolkata"
    assert format_local_datetime(instant,"invalid/timezone")=="12 Sep 2026, 06:54 AM UTC"
    assert format_local_datetime(instant,None)=="12 Sep 2026, 06:54 AM UTC"
    assert format_local_datetime(datetime(2026,9,12,6,54),"Asia/Kolkata")=="12 Sep 2026, 12:24 PM IST"


def test_pdf_priority_topics_branding_metadata_and_attempt_timezone(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=_completed_test(student.id)
        test=db.session.get(AptitudeTest,test_id)
        test.completed_at=datetime(2026,9,12,6,54,tzinfo=timezone.utc)
        test.timezone="Asia/Kolkata"
        test.questions[0].category="Quantitative Aptitude"
        test.questions[0].topic="Profit & Loss"
        db.session.commit()

    response=client.get(f"/api/aptitude/tests/{test_id}/download",headers=auth_headers)
    assert response.status_code==200
    reader=PdfReader(BytesIO(response.data))
    text="\n".join(page.extract_text() or "" for page in reader.pages)
    assert "12 Sep 2026" in text
    assert "12:24 PM IST" in text
    assert "Priority Topics to Improve" in text
    assert "PRIORITY" in text
    assert "Quantitative Aptitude - Profit & Loss" in text
    assert "AptiDARA" not in text
    assert reader.metadata.author=="Aptitude Test"
    assert "AptiDARA" not in (reader.metadata.title or "")


def test_old_attempt_pdf_uses_validated_download_timezone_header(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=_completed_test(student.id)
        test=db.session.get(AptitudeTest,test_id)
        test.completed_at=datetime(2026,9,12,6,54,tzinfo=timezone.utc)
        db.session.commit()

    response=client.get(
        f"/api/aptitude/tests/{test_id}/download",
        headers={**auth_headers,"X-Student-Timezone":"Asia/Kolkata"},
    )
    assert response.status_code==200
    assert "12:24 PM IST" in _pdf_text(response)


def test_pdf_download_enforces_owner_existence_and_completion(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        completed_id=_completed_test(student.id)
        active_id=str(uuid.uuid4())
        db.session.add(AptitudeTest(
            id=active_id,student_id=student.id,status="in_progress",
            total_questions=1,test_mode="mixed",
        ))
        db.session.commit()

    second=client.post("/api/aptitude/auth/register",json={
        "name":"Second Learner","email":"second@example.com",
        "password":"SecurePass123",
    })
    assert second.status_code==201
    second_headers={"Authorization":f"Bearer {second.get_json()['token']}"}

    forbidden=client.get(
        f"/api/aptitude/tests/{completed_id}/download",headers=second_headers,
    )
    assert forbidden.status_code==403
    assert forbidden.get_json()["code"]=="test_forbidden"

    missing=client.get(
        f"/api/aptitude/tests/{uuid.uuid4()}/download",headers=auth_headers,
    )
    assert missing.status_code==404
    assert missing.get_json()["code"]=="test_not_found"

    active=client.get(
        f"/api/aptitude/tests/{active_id}/download",headers=auth_headers,
    )
    assert active.status_code==409
    assert active.get_json()["code"]=="results_unavailable"


def test_technical_pdf_decodes_literal_newlines_and_preserves_code_lines(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=_completed_technical_test(student.id)

    response=client.get(f"/api/aptitude/tests/{test_id}/download",headers=auth_headers)
    assert response.status_code==200
    text=_pdf_text(response)
    assert "Consider this C program:" in text
    assert "#include <stdio.h>" in text
    assert "int main()" in text
    assert "\\n\\n#include" not in text
