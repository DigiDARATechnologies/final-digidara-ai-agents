from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_assessment_creation_uses_one_batch_service_and_navigation_is_stored_only():
    source = (ROOT / "app" / "routes" / "assessment.py").read_text(encoding="utf-8")
    creation = source[source.index("def create_test"):source.index("def status")]
    question = source[source.index("def question("):source.index("def abandon(")]
    answer = source[source.index("def answer("):source.index("def detail(")]

    assert creation.count("generate_and_store_question_batch(test,slots)") == 1
    assert "generate_questions" not in question
    assert "prefetch" not in question
    assert "generate_questions" not in answer
    assert "prefetch" not in answer
    assert "AptitudeTestQuestion.query.filter_by" in question


def test_batch_service_calls_generator_once_for_the_complete_slot_list():
    source = (ROOT / "app" / "services" / "test_question_service.py").read_text(
        encoding="utf-8"
    )
    batch = source[
        source.index("def generate_and_store_question_batch"):
        source.index("def difficulty_metrics")
    ]
    assert batch.count("generate_questions(") == 1
    assert "for sequence, item in enumerate(generated" in batch
    assert "db.session.flush()" in batch
    assert "question_batch_generation" in batch


def test_hint_cache_service_has_no_question_generation_executor():
    source = (ROOT / "app" / "services" / "hint_cache_service.py").read_text(
        encoding="utf-8"
    )
    assert "ThreadPoolExecutor" not in source
    assert "generate_questions" not in source
    assert "cache_hint" in source


def test_background_worker_retires_bank_jobs():
    source = (ROOT / "app" / "services" / "job_service.py").read_text(encoding="utf-8")
    assert '"pool_replenish"' in source
    assert "RETIRED_JOB_TYPES" in source
    assert "generate_bank_batch(" not in source
