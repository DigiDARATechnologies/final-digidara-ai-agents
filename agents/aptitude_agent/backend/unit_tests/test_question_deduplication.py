import pytest
from flask import Flask

from backend.app.services import test_generation
from backend.app.services.question_validation import numeric_pattern, structural_hash, validate_generated_item


SLOT={"category":"Logical Reasoning","topic":"Syllogism","difficulty":"Medium"}


def generated(question):
    return {**SLOT,"question":question,"options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},"correct_answer":"A","explanation":"The stated rule shows that the correct option is A."}


def test_reworded_numeric_scenario_has_same_structural_hash():
    first="A bakery recorded 180, 195, and 210 orders. Which conclusion follows?"
    second="The order totals were 210, 180, and 195. Which conclusion follows?"
    assert structural_hash(first,SLOT["category"],SLOT["topic"])==structural_hash(second,SLOT["category"],SLOT["topic"])


def test_fingerprint_requires_same_topic_and_complete_number_pattern():
    base="The values are 180, 195, and 210."
    assert structural_hash(base,SLOT["category"],SLOT["topic"])!=structural_hash(base,SLOT["category"],"Number Series")
    assert structural_hash(base,SLOT["category"],SLOT["topic"])!=structural_hash("The values are 180, 195, and 225.",SLOT["category"],SLOT["topic"])
    assert structural_hash("The value is 10.",SLOT["category"],SLOT["topic"]) is None


def test_internal_token_and_value_are_rejected():
    with pytest.raises(ValueError,match="internal prompt token"):
        validate_generated_item(generated("A scenario_seed 9698bbf0 appears in this generated question."),SLOT)
    with pytest.raises(ValueError,match="internal seed value"):
        validate_generated_item(generated("A private value 9698bbf0 appears in this generated question."),SLOT,internal_values=("9698bbf0",))


def test_batch_structural_collision_retries(monkeypatch):
    duplicate=generated("Values 210, 180, and 195 appear in another story. Which conclusion follows?")
    first=generated("A code uses values 180, 195, and 210. Which conclusion follows?")
    replacement=generated("Every manager reviews reports, and Kiran is a manager. Which conclusion must hold?")
    responses=[
        ({"questions":[first,duplicate]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}),
        ({"questions":[first,replacement]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}),
    ]
    monkeypatch.setattr(test_generation,"json_completion",lambda *_args,**_kwargs:responses.pop(0))
    app=Flask(__name__);app.config.update(OPENAI_API_KEY="test",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():questions,_model,usage=test_generation.generate_questions([SLOT,SLOT])
    assert questions[0]["structural_hash"]!=questions[1]["structural_hash"]
    assert usage["total_tokens"]==60


def test_persistent_batch_collision_stops_after_three_attempts(monkeypatch):
    first=generated("A code uses values 180, 195, and 210. Which conclusion follows?")
    duplicate=generated("Values 210, 180, and 195 appear elsewhere. Which conclusion follows?")
    calls=[]

    def repeated(*_args,**_kwargs):
        calls.append(True)
        return {"questions":[first,duplicate]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}

    monkeypatch.setattr(test_generation,"json_completion",repeated)
    app=Flask(__name__);app.config.update(OPENAI_API_KEY="test",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context(),pytest.raises(ValueError,match="after 3 attempts"):
        test_generation.generate_questions([SLOT,SLOT])
    assert len(calls)==3


def test_numeric_pattern_preserves_multiplicity_and_percent_type():
    assert numeric_pattern("An item costs 800 after a 15% discount from 800 units.")==["number:800","number:800","percent:15"]


def test_prompt_and_validator_share_the_full_exclusion_set(monkeypatch):
    exclusions=[f"Archived learner scenario {index}: determine whether statement {index} follows." for index in range(25)]
    rejected=generated(exclusions[-1])
    accepted=generated("A museum curator applies a syllogistic rule to a newly catalogued exhibit. Which conclusion follows?")
    prompts=[]
    responses=[
        ({"questions":[rejected]},{"input_tokens":20,"output_tokens":10,"total_tokens":30,"model":"fallback-model"}),
        ({"questions":[accepted]},{"input_tokens":20,"output_tokens":10,"total_tokens":30,"model":"fallback-model"}),
    ]

    def fake_completion(_system,prompt,_temperature,**_kwargs):
        prompts.append(prompt)
        return responses.pop(0)

    monkeypatch.setattr(test_generation,"json_completion",fake_completion)
    app=Flask(__name__);app.config.update(OPENAI_API_KEY="test",OPENAI_MODEL="primary-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():questions,model,_usage=test_generation.generate_questions([SLOT],avoid_questions=exclusions)

    assert all(question in prompts[0] for question in exclusions)
    assert exclusions[-1] in prompts[0]
    assert exclusions[-1] in prompts[1]
    assert "Required variation:" in prompts[1]
    assert questions[0]["question"]==accepted["question"]
    assert model=="fallback-model"


def test_retry_context_accumulates_all_rejected_questions(monkeypatch):
    exclusions=[
        "A library rule says all archived books are indexed. Which conclusion follows?",
        "A factory rule says every inspected part receives a label. Which conclusion follows?",
    ]
    first=generated(exclusions[0])
    second=generated(exclusions[1])
    accepted=generated("A botanical garden classifies every native seed in its registry. Which conclusion follows?")
    prompts=[]
    responses=[
        ({"questions":[first]},{"input_tokens":10,"output_tokens":5,"total_tokens":15}),
        ({"questions":[second]},{"input_tokens":10,"output_tokens":5,"total_tokens":15}),
        ({"questions":[accepted]},{"input_tokens":10,"output_tokens":5,"total_tokens":15}),
    ]

    def fake_completion(_system,prompt,_temperature,**_kwargs):
        prompts.append(prompt)
        return responses.pop(0)

    monkeypatch.setattr(test_generation,"json_completion",fake_completion)
    app=Flask(__name__);app.config.update(OPENAI_API_KEY="test",OPENAI_MODEL="primary-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():questions,_model,usage=test_generation.generate_questions([SLOT],avoid_questions=exclusions)

    assert len(prompts)==3
    assert first["question"] in prompts[1]
    assert first["question"] in prompts[2]
    assert second["question"] in prompts[2]
    assert "different real-world setting" in prompts[1]
    assert "different facet" in prompts[2]
    assert questions[0]["question"]==accepted["question"]
    assert usage["total_tokens"]==45
