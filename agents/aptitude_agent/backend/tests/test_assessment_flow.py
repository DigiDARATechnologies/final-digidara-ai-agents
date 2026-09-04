import importlib
import uuid
import pytest

from backend.app.extensions import db
from backend.app.models import AIRecommendation, AptitudeAnswer, AptitudeTest, AptitudeTestQuestion, BackgroundJob, LearnerLastTopics, QuestionBankItem, Student
from backend.app.models.base import utcnow
from backend.app.services.evaluation_service import evaluate_answer
from backend.app.services.test_generation import build_slots
from backend.app.services.topic_selection_service import SHARED_HISTORY_SCOPE
from backend.app.topic_config import topic_is_starred


REMOVED_DIAGNOSTIC_FIELDS = {
    "confidence_rating",
    "confidence_calibration",
    "reasoning_text",
    "reasoning_quality",
    "reasoning_feedback",
    "reasoning_summary",
    "mistake_type",
    "mistake_explanation",
    "mistake_breakdown",
    "diagnostics_status",
    "diagnostics_error",
    "outcome_type",
}


def _assert_diagnostics_absent(payload):
    if isinstance(payload, dict):
        assert REMOVED_DIAGNOSTIC_FIELDS.isdisjoint(payload)
        for value in payload.values():
            _assert_diagnostics_absent(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_diagnostics_absent(value)


def test_answer_evaluation_is_authoritative_and_local():
    question = type("Question", (), {"correct_answer": "C"})()
    assert evaluate_answer(question, "C") == (True, "authoritative")
    assert evaluate_answer(question, "A") == (False, "authoritative")


def test_answer_without_diagnostics_completes_and_exposes_no_diagnostic_data(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").one()
        test_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())
        test = AptitudeTest(
            id=test_id,
            student_id=student.id,
            status="in_progress",
            current_sequence=1,
            total_questions=1,
            test_mode="mixed",
        )
        question = AptitudeTestQuestion(
            id=question_id,
            test_id=test_id,
            sequence_no=1,
            category="Logical Reasoning",
            topic="Series",
            difficulty="Easy",
            difficulty_reason="Test fixture",
            question_text="What comes next: 2, 4, 6, ?",
            option_a="7",
            option_b="8",
            option_c="9",
            option_d="10",
            correct_answer="B",
            explanation="The sequence increases by 2, so the answer is 8.",
            question_started_at=utcnow(),
            generation_model="test-fixture",
            content_hash=f"test-{question_id}",
        )
        db.session.add_all([test, question])
        db.session.commit()

    response = client.post(
        f"/api/aptitude/tests/{test_id}/answer",
        headers=auth_headers,
        json={"selected_answer": "B"},
    )
    assert response.status_code == 200
    answer_payload = response.get_json()
    assert answer_payload["is_correct"] is True
    assert answer_payload["complete"] is True
    _assert_diagnostics_absent(answer_payload)

    with app.app_context():
        assert (
            BackgroundJob.query.filter_by(
                test_id=test_id, job_type="answer_diagnostics"
            ).count()
            == 0
        )
        assert (
            BackgroundJob.query.filter_by(
                test_id=test_id, job_type="recommendation"
            ).count()
            == 0
        )

    assessment_routes=importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(
        assessment_routes,"generate_recommendation",
        lambda *_args,**_kwargs:(
            "Focus on logical sequences and review the questions you missed.",
            "test-model",
            {"input_tokens":0,"output_tokens":0,"total_tokens":0,"model":"test-model"},
        ),
    )

    detail_response = client.get(
        f"/api/aptitude/tests/{test_id}", headers=auth_headers
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    _assert_diagnostics_absent(detail_payload)
    assert detail_payload["recommendation"]=="Focus on logical sequences and review the questions you missed."
    assert detail_payload["recommendation_status"]=="completed"
    assert detail_payload["questions"][0]["selected_answer"] == "B"
    assert detail_payload["questions"][0]["is_correct"] is True


def test_results_returns_final_recommendation_fallback_without_worker(app,client,auth_headers,monkeypatch):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=str(uuid.uuid4())
        db.session.add(AptitudeTest(
            id=test_id,student_id=student.id,status="completed",current_sequence=1,
            total_questions=0,test_mode="mixed",score=0,percentage=0,completed_at=utcnow(),
        ))
        db.session.commit()

    def unavailable(*_args,**_kwargs):
        raise RuntimeError("provider unavailable")
    assessment_routes=importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(assessment_routes,"generate_recommendation",unavailable)

    response=client.get(f"/api/aptitude/tests/{test_id}",headers=auth_headers)
    assert response.status_code==200
    payload=response.get_json()
    assert payload["recommendation_status"]=="failed"
    assert "Review your incorrect answers" in payload["recommendation"]

    with app.app_context():
        saved=AIRecommendation.query.filter_by(test_id=test_id).one()
        assert saved.status=="failed"
        assert saved.model_version=="deterministic-fallback"
        assert BackgroundJob.query.filter_by(test_id=test_id,job_type="recommendation").count()==0

    monkeypatch.setattr(
        assessment_routes,"generate_recommendation",
        lambda *_args,**_kwargs:(
            "Review foundational concepts, then complete one short timed drill.",
            "recovered-model",
            {"input_tokens":1,"output_tokens":1,"total_tokens":2,"model":"recovered-model"},
        ),
    )
    recovered=client.get(f"/api/aptitude/tests/{test_id}",headers=auth_headers)
    assert recovered.status_code==200
    assert recovered.get_json()["recommendation_status"]=="completed"
    assert recovered.get_json()["recommendation"].startswith("Review foundational concepts")
    with app.app_context():
        saved=AIRecommendation.query.filter_by(test_id=test_id).one()
        assert saved.attempt_count==2
        assert saved.status=="completed"
        assert saved.last_error is None


def test_start_test_ignores_legacy_bank_and_uses_live_generation(app,client,auth_headers,monkeypatch):
    slot={**build_slots()[0],"difficulty":"Medium"}
    bank_id=str(uuid.uuid4())
    with app.app_context():
        db.session.add(QuestionBankItem(
            id=bank_id,category=slot["category"],topic=slot["topic"],difficulty=slot["difficulty"],
            question_text="Which approved bank question is served without contacting Groq?",
            option_a="The stored approved question",option_b="A live retry",option_c="A browser cache",option_d="An empty response",
            correct_answer="A",explanation="The approved MySQL item is selected before any live provider call.",
            hint_text="Identify which source is checked first.",content_hash=f"bank-{bank_id}",status="approved",source_model="bank-test",
        ))
        db.session.commit()

    calls=[]
    def live_generation(slots,*_args,**_kwargs):
        calls.append(slots[0])
        generated_slot=slots[0]
        return [{
            **generated_slot,
            "question":"Which source now creates every learner question?",
            "options":{"A":"Live Groq","B":"Approved bank","C":"Browser storage","D":"A static file"},
            "correct_answer":"A",
            "explanation":"Live Groq generates the question for this attempt.",
            "content_hash":"live-generation-test-hash",
            "structural_hash":"live-generation-test-structure",
        }],"live-test-model",{"input_tokens":10,"output_tokens":5,"total_tokens":15}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    response=client.post("/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"})
    assert response.status_code==201,response.get_json()
    test_id=response.get_json()["test_id"]

    with app.app_context():
        question=AptitudeTestQuestion.query.filter_by(test_id=test_id,sequence_no=1).one()
        bank_item=db.session.get(QuestionBankItem,bank_id)
        assert calls
        assert question.source_bank_item_id is None
        assert question.generation_model=="live-test-model"
        assert bank_item.times_used==0


def test_start_test_rate_limit_uses_runtime_config_and_returns_retry_time(app,client,auth_headers,monkeypatch):
    monkeypatch.setitem(app.config,"START_TEST_RATE_LIMIT",1)
    monkeypatch.setitem(app.config,"START_TEST_RATE_WINDOW_SECONDS",60)

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0]
        return [{
            **slot,
            "question":"Which response confirms the configurable start limit test?",
            "options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"First is the configured correct response.",
            "content_hash":"configurable-rate-limit-content",
            "structural_hash":"configurable-rate-limit-structure",
        }],"rate-limit-test-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    first=client.post("/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"})
    assert first.status_code==201,first.get_json()

    blocked=client.post("/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"})
    assert blocked.status_code==429
    payload=blocked.get_json()
    assert payload["code"]=="rate_limited"
    assert 1<=payload["details"]["retry_after_seconds"]<=60


def test_category_practice_rotates_topics_between_consecutive_attempts(app,client,auth_headers,monkeypatch):
    calls=[]

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0];calls.append(dict(slot))
        suffix=str(len(calls))
        return [{
            **slot,
            "question":f"Generated rotation question {suffix} for {slot['topic']}?",
            "options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"First is the configured correct response.",
            "content_hash":f"rotation-content-{suffix}",
            "structural_hash":f"rotation-structure-{suffix}",
        }],"rotation-test-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    payload={"mode":"category_practice","category":"Computer Fundamentals","level":"Beginner"}

    first=client.post("/api/aptitude/tests",headers=auth_headers,json=payload)
    assert first.status_code==201,first.get_json()
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        row=LearnerLastTopics.query.filter_by(
            learner_id=student.id,category_id=payload["category"],level=SHARED_HISTORY_SCOPE,
        ).one()
        first_topics=list(row.topics_used)

    second=client.post("/api/aptitude/tests",headers=auth_headers,json=payload)
    assert second.status_code==201,second.get_json()
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        rows=LearnerLastTopics.query.filter_by(
            learner_id=student.id,category_id=payload["category"],level=SHARED_HISTORY_SCOPE,
        ).all()
        assert len(rows)==1
        second_topics=list(rows[0].topics_used)
        first_test=db.session.get(AptitudeTest,first.get_json()["test_id"])
        assert first_test.status=="abandoned"

    assert len(first_topics)==10
    assert len(second_topics)==10
    assert len(set(first_topics))==10
    assert len(set(second_topics))==10
    assert first_topics!=second_topics
    legacy_fixed_order=[
        "Operating Systems","Networking Basics","Database Basics",
        "Computer Architecture","Cybersecurity",
    ]
    assert first_topics!=legacy_fixed_order
    assert second_topics!=legacy_fixed_order
    assert calls[0]["topic"]==first_topics[0]
    assert calls[1]["topic"]==second_topics[0]


def test_mixed_and_category_practice_share_topic_rotation_history(app,client,auth_headers,monkeypatch):
    generation_count=0

    def live_generation(slots,*_args,**_kwargs):
        nonlocal generation_count
        generation_count+=1
        slot=slots[0]
        return [{
            **slot,
            "question":f"Shared history generation {generation_count} for {slot['topic']}?",
            "options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"First is the configured correct response.",
            "content_hash":f"shared-history-content-{generation_count}",
            "structural_hash":f"shared-history-structure-{generation_count}",
        }],"shared-history-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)

    first_mixed=client.post("/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"})
    assert first_mixed.status_code==201,first_mixed.get_json()
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        first_rows=LearnerLastTopics.query.filter_by(
            learner_id=student.id,level=SHARED_HISTORY_SCOPE,
        ).all()
        assert len(first_rows)==6
        first_topics={row.category_id:list(row.topics_used) for row in first_rows}
        first_test=db.session.get(AptitudeTest,first_mixed.get_json()["test_id"])
        first_schedule=build_slots(
            seed=first_test.id,category_counts=first_test.mixed_category_counts,
            topics_by_category=first_topics,
        )
        first_question=AptitudeTestQuestion.query.filter_by(test_id=first_test.id,sequence_no=1).one()
        assert first_question.topic==first_schedule[0]["topic"]

    category="Quantitative Aptitude"
    practice=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"category_practice","category":category,"level":"Beginner"},
    )
    assert practice.status_code==201,practice.get_json()
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        shared=LearnerLastTopics.query.filter_by(
            learner_id=student.id,category_id=category,level=SHARED_HISTORY_SCOPE,
        ).one()
        practice_topics=list(shared.topics_used)
    first_nonstarred={topic for topic in first_topics[category] if not topic_is_starred(category,topic)}
    practice_nonstarred={topic for topic in practice_topics if not topic_is_starred(category,topic)}
    # Category Practice remains unchanged: its priority topics may repeat,
    # while its non-priority topics respect the shared history.
    assert first_nonstarred.isdisjoint(practice_nonstarred)

    second_mixed=client.post("/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"})
    assert second_mixed.status_code==201,second_mixed.get_json()
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        second_rows=LearnerLastTopics.query.filter_by(
            learner_id=student.id,level=SHARED_HISTORY_SCOPE,
        ).all()
        assert len(second_rows)==6
        second_topics={row.category_id:list(row.topics_used) for row in second_rows}

    for current_category in first_topics:
        previous=(practice_topics if current_category==category else first_topics[current_category])
        # Mixed Test treats priority metadata as irrelevant: every topic from
        # the last shared attempt is rotated behind fresh candidates.
        assert set(previous).isdisjoint(second_topics[current_category])


def test_technical_category_defaults_to_python_and_exposes_language(app,client,auth_headers,monkeypatch):
    captured=[]

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0];captured.append(dict(slot))
        return [{
            **slot,
            "question":"Which language is selected for this technical practice?",
            "options":{"A":"Python","B":"Java","C":"C","D":"SQL"},
            "correct_answer":"A",
            "explanation":"The default selected language is Python, so option A is correct.",
            "content_hash":"technical-default-language-content",
            "structural_hash":"technical-default-language-structure",
        }],"technical-language-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    created=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"category_practice","category":"Technical Aptitude","level":"Beginner"},
    )
    assert created.status_code==201,created.get_json()
    test_id=created.get_json()["test_id"]
    question=client.get(f"/api/aptitude/tests/{test_id}/question",headers=auth_headers)
    assert question.status_code==200,question.get_json()
    assert question.get_json()["technical_language"]=="Python"
    with app.app_context():
        assert db.session.get(AptitudeTest,test_id).technical_language=="Python"
    assert captured[0]["technical_language"]=="Python"


@pytest.mark.parametrize(
    ("level","difficulty","allowed_seconds"),
    [("Beginner","Easy",60),("Intermediate","Medium",90),("Advanced","Hard",120)],
)
def test_category_question_timer_is_persisted_from_difficulty(
    level,difficulty,allowed_seconds,app,client,auth_headers,monkeypatch,
):
    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0]
        return [{
            **slot,
            "question":f"Which timer applies to this {level} practice question?",
            "options":{"A":"Configured tier","B":"Fixed minute","C":"No timer","D":"Browser only"},
            "correct_answer":"A",
            "explanation":"The configured difficulty tier determines the authoritative timer.",
            "content_hash":f"timer-{level.casefold()}-content",
            "structural_hash":f"timer-{level.casefold()}-structure",
        }],"timer-test-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    created=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"category_practice","category":"Logical Reasoning","level":level},
    )
    assert created.status_code==201,created.get_json()
    test_id=created.get_json()["test_id"]
    served=client.get(f"/api/aptitude/tests/{test_id}/question",headers=auth_headers)
    assert served.status_code==200,served.get_json()
    assert served.get_json()["difficulty"]==difficulty
    assert served.get_json()["allowed_seconds"]==allowed_seconds
    assert served.get_json()["remaining_seconds"]==allowed_seconds
    with app.app_context():
        saved=AptitudeTestQuestion.query.filter_by(test_id=test_id,sequence_no=1).one()
        assert saved.allowed_time_seconds==allowed_seconds


@pytest.mark.parametrize("category",["Logical Reasoning","Verbal Ability"])
def test_category_practice_completes_ten_questions_and_reports_ten(category,app,client,auth_headers,monkeypatch):
    calls=[]

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0];number=len(calls)+1;calls.append(dict(slot))
        return [{
            **slot,
            "question":f"Ten-question practice item {number} for {slot['topic']}?",
            "options":{"A":"Correct","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"Correct is the configured answer.",
            "content_hash":f"ten-practice-content-{number}",
            "structural_hash":f"ten-practice-structure-{number}",
        }],"ten-practice-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    assessment_routes=importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    monkeypatch.setattr("backend.app.services.adaptive_service.questions_are_near_duplicates",lambda *_args,**_kwargs:False)
    monkeypatch.setattr(assessment_routes,"schedule_next_question_prefetch",lambda *_args,**_kwargs:None)
    monkeypatch.setattr(assessment_routes,"schedule_test_prefetch",lambda *_args,**_kwargs:None)
    monkeypatch.setattr(
        assessment_routes,"generate_recommendation",
        lambda *_args,**_kwargs:(
            "Continue practising the topics reviewed in this session.",
            "test-model",{"input_tokens":0,"output_tokens":0,"total_tokens":0,"model":"test-model"},
        ),
    )

    created=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"category_practice","category":category,"level":"Beginner"},
    )
    assert created.status_code==201,created.get_json()
    test_id=created.get_json()["test_id"]

    served_topics=[]
    for sequence in range(1,11):
        question=client.get(f"/api/aptitude/tests/{test_id}/question",headers=auth_headers)
        assert question.status_code==200,question.get_json()
        question_payload=question.get_json()
        assert question_payload["sequence"]==sequence
        assert question_payload["total"]==10
        served_topics.append(question_payload["topic"])
        answered=client.post(
            f"/api/aptitude/tests/{test_id}/answer",headers=auth_headers,
            json={"selected_answer":"A"},
        )
        assert answered.status_code==200,answered.get_json()
        assert answered.get_json()["complete"]==(sequence==10)

    assert len(served_topics)==10
    assert len(set(served_topics))==10
    assert len(calls)==10

    detail=client.get(f"/api/aptitude/tests/{test_id}",headers=auth_headers)
    assert detail.status_code==200,detail.get_json()
    assert detail.get_json()["total"]==10
    assert detail.get_json()["score"]==10
    assert len(detail.get_json()["questions"])==10

    history=client.get("/api/aptitude/history",headers=auth_headers)
    assert history.status_code==200,history.get_json()
    saved=next(item for item in history.get_json()["tests"] if item["id"]==test_id)
    assert saved["total"]==10
    assert saved["score"]==10


def test_category_practice_retries_invalid_content_with_a_different_topic(app,client,auth_headers,monkeypatch):
    calls=[]

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0];calls.append(dict(slot))
        if len(calls)==1:
            raise ValueError("topic-specific generated content was invalid")
        return [{
            **slot,
            "question":f"Replacement topic question for {slot['topic']}?",
            "options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"First is the configured correct response.",
            "content_hash":"replacement-content",
            "structural_hash":"replacement-structure",
        }],"rotation-test-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    response=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"category_practice","category":"Verbal Ability","level":"Intermediate"},
    )
    assert response.status_code==201,response.get_json()
    assert len(calls)==2
    assert calls[0]["topic"]!=calls[1]["topic"]

    with app.app_context():
        test=db.session.get(AptitudeTest,response.get_json()["test_id"])
        history=LearnerLastTopics.query.filter_by(
            learner_id=test.student_id,category_id=test.selected_category,level=SHARED_HISTORY_SCOPE,
        ).one()
        question=AptitudeTestQuestion.query.filter_by(test_id=test.id,sequence_no=1).one()
        assert history.topics_used[0]==calls[1]["topic"]
        assert question.topic==calls[1]["topic"]


def test_next_question_live_failure_is_explicit_and_keeps_attempt_retryable(app,client,auth_headers,monkeypatch):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=str(uuid.uuid4());question_id=str(uuid.uuid4())
        test=AptitudeTest(
            id=test_id,student_id=student.id,status="in_progress",current_sequence=2,
            total_questions=10,test_mode="category_practice",
            selected_category="Quantitative Aptitude",selected_level="Beginner",hints_allowed=2,
        )
        question=AptitudeTestQuestion(
            id=question_id,test_id=test_id,sequence_no=1,category="Quantitative Aptitude",topic="Percentages",
            difficulty="Easy",question_text="What is ten percent of one hundred?",
            option_a="10",option_b="20",option_c="30",option_d="40",correct_answer="A",
            explanation="Step 1: Multiply 100 by 10%. Step 2: Answer = 10.",
            question_started_at=utcnow(),generation_model="test-fixture",content_hash=f"failure-{question_id}",
        )
        answer=AptitudeAnswer(
            id=str(uuid.uuid4()),test_id=test_id,student_id=student.id,question_id=question_id,
            selected_answer="A",correct_answer="A",is_correct=True,timed_out=False,
            time_taken_seconds=10,evaluation_source="authoritative",
        )
        db.session.add_all([test,question,answer]);db.session.commit()

    calls=[]
    def invalid_live_generation(*_args,**_kwargs):
        calls.append(True)
        raise ValueError("forced live validation failure")

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",invalid_live_generation)
    response=client.get(f"/api/aptitude/tests/{test_id}/question",headers=auth_headers)
    assert response.status_code==503
    assert response.get_json()["code"]=="question_generation_failed"
    assert "prepare the next question" in response.get_json()["error"].lower()
    assert len(calls)==2

    with app.app_context():
        saved_test=db.session.get(AptitudeTest,test_id)
        assert saved_test.status=="in_progress"
        assert saved_test.current_sequence==2
        assert AptitudeTestQuestion.query.filter_by(test_id=test_id).count()==1
        assert AptitudeAnswer.query.filter_by(test_id=test_id).count()==1


def test_hint_returns_topic_fallback_when_groq_is_not_configured(app,client,auth_headers):
    with app.app_context():
        student=Student.query.filter_by(email="learner@example.com").one()
        test_id=str(uuid.uuid4());question_id=str(uuid.uuid4())
        test=AptitudeTest(
            id=test_id,student_id=student.id,status="in_progress",current_sequence=1,
            total_questions=1,test_mode="mixed",hints_allowed=3,
        )
        question=AptitudeTestQuestion(
            id=question_id,test_id=test_id,sequence_no=1,category="Quantitative Aptitude",topic="Time & Work",
            difficulty="Easy",question_text="Two workers complete a task together. Which method should be used?",
            option_a="Add work rates",option_b="Subtract ages",option_c="Sort letters",option_d="Count vowels",
            correct_answer="A",explanation="Work-rate problems are solved by combining individual rates.",
            question_started_at=utcnow(),generation_model="test-fixture",content_hash=f"hint-{question_id}",
        )
        db.session.add_all([test,question]);db.session.commit()

    response=client.post(f"/api/aptitude/tests/{test_id}/hint",headers=auth_headers)
    assert response.status_code==200
    payload=response.get_json()
    assert payload["hint"]
    second=client.post(f"/api/aptitude/tests/{test_id}/hint",headers=auth_headers)
    assert second.status_code==200
    assert second.get_json()["hint"]==payload["hint"]
    with app.app_context():
        saved_question=db.session.get(AptitudeTestQuestion,question_id)
        saved_test=db.session.get(AptitudeTest,test_id)
        assert saved_question.hint_text is None
        assert saved_question.hint_requested is True
        assert saved_test.hints_used==1
    assert payload["hints_used"]==1
    assert payload["hints_remaining"]==2
