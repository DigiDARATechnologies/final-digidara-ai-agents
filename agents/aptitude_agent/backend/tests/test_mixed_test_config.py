from backend.app.extensions import db
from backend.app.models import AptitudeTest, LearnerMixedTestConfig
from backend.app.services.test_generation import CATEGORIES, build_slots


DEFAULTS = {
    "quantitative_aptitude": 5,
    "logical_reasoning": 4,
    "verbal_ability": 3,
    "analytical_reasoning": 3,
    "computer_fundamentals": 3,
    "technical_aptitude": 3,
}


def payload(counts):
    return {
        "categories": [
            {"category_id": category_id, "question_count": count}
            for category_id, count in counts.items()
        ]
    }


def test_get_seeds_six_default_rows(app,client,auth_headers):
    response=client.get("/api/learner/mixed-test-config",headers=auth_headers)
    assert response.status_code==200,response.get_json()
    data=response.get_json()
    assert data["total_questions"]==21
    assert {item["category_id"]:item["question_count"] for item in data["categories"]}==DEFAULTS
    assert data["limits"]=={"min_per_category":3,"max_per_category":10,"max_total":60}
    with app.app_context():
        assert LearnerMixedTestConfig.query.count()==6


def test_put_updates_categories_independently_and_validates_bounds(client,auth_headers):
    counts={**DEFAULTS,"logical_reasoning":10}
    response=client.put(
        "/api/learner/mixed-test-config",headers=auth_headers,json=payload(counts),
    )
    assert response.status_code==200,response.get_json()
    assert response.get_json()["total_questions"]==27
    assert {
        item["category_id"]:item["question_count"]
        for item in response.get_json()["categories"]
    }==counts

    below_minimum={**DEFAULTS,"technical_aptitude":2}
    rejected=client.put(
        "/api/learner/mixed-test-config",headers=auth_headers,json=payload(below_minimum),
    )
    assert rejected.status_code==400
    assert "between 3 and 10" in rejected.get_json()["error"]

    invalid={**DEFAULTS,"technical_aptitude":11}
    rejected=client.put(
        "/api/learner/mixed-test-config",headers=auth_headers,json=payload(invalid),
    )
    assert rejected.status_code==400
    assert "between 3 and 10" in rejected.get_json()["error"]


def test_mixed_test_uses_saved_count_snapshot(app,client,auth_headers,monkeypatch):
    counts={**DEFAULTS,"logical_reasoning":10}
    updated=client.put(
        "/api/learner/mixed-test-config",headers=auth_headers,json=payload(counts),
    )
    assert updated.status_code==200,updated.get_json()

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0]
        return [{
            **slot,
            "question":f"Configured Mixed Test question for {slot['topic']}?",
            "options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},
            "correct_answer":"A",
            "explanation":"First is the configured correct response.",
            "content_hash":"mixed-config-content",
            "structural_hash":"mixed-config-structure",
        }],"mixed-config-test-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    created=client.post(
        "/api/aptitude/tests",headers=auth_headers,json={"mode":"mixed"},
    )
    assert created.status_code==201,created.get_json()
    with app.app_context():
        test=db.session.get(AptitudeTest,created.get_json()["test_id"])
        assert test.total_questions==27
        assert test.mixed_category_counts=={
            "Quantitative Aptitude":5,
            "Logical Reasoning":10,
            "Verbal Ability":3,
            "Analytical Reasoning":3,
            "Computer Fundamentals":3,
            "Technical Aptitude":3,
        }
        schedule=build_slots(seed=test.id,category_counts=test.mixed_category_counts)
        assert len(schedule)==27
        assert sum(row["category"]=="Quantitative Aptitude" for row in schedule)==5
        assert sum(row["category"]=="Logical Reasoning" for row in schedule)==10
        assert set(test.mixed_category_counts)==set(CATEGORIES)


def test_mixed_test_persists_selected_technical_language(app,client,auth_headers,monkeypatch):
    captured=[]

    def live_generation(slots,*_args,**_kwargs):
        slot=slots[0];captured.append(dict(slot))
        return [{
            **slot,
            "question":"Which option verifies language persistence?",
            "options":{"A":"Stored","B":"Missing","C":"Invalid","D":"Unknown"},
            "correct_answer":"A",
            "explanation":"The selected language is stored with the test, so option A is correct.",
            "content_hash":"mixed-language-content",
            "structural_hash":"mixed-language-structure",
        }],"mixed-language-model",{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr("backend.app.services.adaptive_service.generate_questions",live_generation)
    created=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"mixed","technical_language":"SQL"},
    )
    assert created.status_code==201,created.get_json()
    with app.app_context():
        test=db.session.get(AptitudeTest,created.get_json()["test_id"])
        assert test.technical_language=="SQL"
        schedule=build_slots(
            seed=test.id,category_counts=test.mixed_category_counts,
            technical_language=test.technical_language,
        )
        assert all(
            slot["technical_language"]=="SQL"
            for slot in schedule if slot["category"]=="Technical Aptitude"
        )
        assert all(
            "technical_language" not in slot
            for slot in schedule if slot["category"]!="Technical Aptitude"
        )
    assert captured


def test_test_creation_rejects_unknown_technical_language(client,auth_headers):
    response=client.post(
        "/api/aptitude/tests",headers=auth_headers,
        json={"mode":"mixed","technical_language":"JavaScript"},
    )
    assert response.status_code==400
    assert response.get_json()["code"]=="invalid_technical_language"


def test_build_slots_rejects_a_category_below_minimum():
    counts={category:3 for category in CATEGORIES}
    counts["Quantitative Aptitude"]=2
    try:
        build_slots(seed="below-minimum-test",category_counts=counts)
    except ValueError as exc:
        assert "between 3 and 10" in str(exc)
    else:
        raise AssertionError("Expected an invalid Mixed Test category count")


def test_build_slots_supports_sixty_question_safety_ceiling():
    counts={category:10 for category in CATEGORIES}
    schedule=build_slots(seed="sixty-question-test",category_counts=counts)
    assert len(schedule)==60
    for category in CATEGORIES:
        assert sum(row["category"]==category for row in schedule)==10
