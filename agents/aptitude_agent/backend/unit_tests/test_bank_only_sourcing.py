from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def test_learner_question_selector_is_memory_prefetch_then_bounded_live():
    source=(ROOT/"app"/"services"/"adaptive_service.py").read_text(encoding="utf-8")
    selector=source[source.index("def _question_source"):source.index("def _persist_question")]
    assert "generate_questions(" in selector
    assert 'allow_demo_fallback=current_app.config["ALLOW_DEMO_QUESTIONS"]' in selector
    assert "consume_question_prefetch(" in selector
    assert '"prefetch_hit"' in selector
    assert '"prefetch_miss"' in selector
    assert '"expected_first_question"' in selector
    assert "select_approved_item(" not in selector
    assert 'max_validation_attempts=1 if test.test_mode=="category_practice" else 2' in selector
    assert "replace_attempt_topic(" in selector


def test_background_worker_retires_bank_and_persistent_prefetch_jobs():
    source=(ROOT/"app"/"services"/"job_service.py").read_text(encoding="utf-8")
    assert '"pool_replenish"' in source
    assert "RETIRED_JOB_TYPES" in source
    assert "generate_bank_batch(" not in source
