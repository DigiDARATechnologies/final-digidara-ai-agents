from flask import Flask

from backend.app.services.usage_service import record_usage


def test_operational_job_usage_is_supported_without_a_learner():
    app=Flask(__name__)
    app.config.update(GROQ_INPUT_COST_PER_MILLION=.15,GROQ_OUTPUT_COST_PER_MILLION=.60)
    with app.app_context():
        event=record_usage(None,"question_bank_replenishment","test",{"input_tokens":6,"output_tokens":4,"total_tokens":10})
    assert event.student_id is None
    assert event.operation=="question_bank_replenishment"
