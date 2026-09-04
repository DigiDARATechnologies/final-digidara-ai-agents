import threading
import time

from backend.app.services.prefetch_service import (
    clear_test_cache,
    consume_question_prefetch,
    schedule_question_prefetch,
)


def test_question_prefetch_is_ephemeral_nonblocking_and_single_use(app,monkeypatch):
    ready=threading.Event()
    slot={"category":"Logical Reasoning","topic":"Number Series","difficulty":"Medium"}
    item={
        **slot,
        "question":"Which number follows the supplied sequence?",
        "options":{"A":"10","B":"11","C":"12","D":"13"},
        "correct_answer":"C",
        "explanation":"The sequence rule produces 12.",
        "content_hash":"prefetch-content",
        "structural_hash":"prefetch-structure",
    }

    def fake_generate(*_args,**_kwargs):
        ready.set()
        return [item],"prefetch-model",{
            "input_tokens":5,"output_tokens":3,"total_tokens":8,
            "provider_wait_ms":4,"validation_attempt_count":1,
        }

    monkeypatch.setattr("backend.app.services.test_generation.generate_questions",fake_generate)
    with app.app_context():
        clear_test_cache("prefetch-test")
        assert schedule_question_prefetch("prefetch-test",2,slot,[]) is True
        assert ready.wait(2)

    # The worker publishes immediately after returning from fake_generate;
    # this wait is test synchronization, never application serve behavior.
    time.sleep(.05)
    result=consume_question_prefetch("prefetch-test",2,slot)
    assert result is not None
    assert result["item"]["question"]==item["question"]
    assert result["model"]=="prefetch-model"
    assert consume_question_prefetch("prefetch-test",2,slot) is None
