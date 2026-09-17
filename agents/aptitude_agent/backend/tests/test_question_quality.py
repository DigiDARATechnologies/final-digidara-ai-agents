import pytest
from flask import Flask

from backend.app.services import test_generation
from backend.app.services.question_validation import numeric_pattern, structural_hash, validate_generated_item


SLOT={"category":"Quantitative Aptitude","topic":"Average","difficulty":"Medium"}
LOGICAL_SLOT={"category":"Logical Reasoning","topic":"Syllogism","difficulty":"Medium"}
TECHNICAL_SLOT={"category":"Technical Aptitude","topic":"Programming Fundamentals","difficulty":"Easy","technical_language":"Java"}


def item(explanation="Step 1: 10 + 10 = 20. Step 2: Verify the addition once. Step 3: Answer = 20."):
    return {
        **SLOT,
        "question":"What is the average value in this short example?",
        "options":{"A":"10","B":"15","C":"20","D":"25"},
        "correct_answer":"C",
        "explanation":explanation,
    }


def test_accepts_short_consistent_step_explanation():
    assert validate_generated_item(item(),SLOT)["correct_answer"]=="C"


def test_accepts_derived_answer_reused_across_math_steps():
    explanation="Step 1: Add the two parts: 12 + 8 = 20. Step 2: Carry the derived total of 20 into the final comparison. Step 3: Answer = 20."
    assert validate_generated_item(item(explanation),SLOT)["explanation"]==(
        "Step 1: Add the two parts: 12 + 8 = 20.\n"
        "Step 2: Carry the derived total of 20 into the final comparison.\n"
        "Step 3: Answer = 20."
    )


def test_accepts_calculation_and_answer_in_same_final_step():
    explanation="Step 1: Add the values. Step 2: 12 + 8 = 20. Answer = 20."
    assert validate_generated_item(item(explanation),SLOT)["explanation"]==(
        "Step 1: Add the values.\n"
        "Step 2: 12 + 8 = 20. Answer = 20."
    )


def test_accepts_equivalent_thousands_separator_in_derivation():
    generated=item("Step 1: Add the values. Step 2: 700 + 550 = 1250. Step 3: Answer = 1,250.")
    generated["options"]={"A":"1,000","B":"1,100","C":"1,250","D":"1,500"}
    assert validate_generated_item(generated,SLOT)["correct_answer"]=="C"


def test_rejects_long_explanation():
    with pytest.raises(ValueError,match="600 characters"):
        validate_generated_item(item("Analysis "*80+"Answer = 20."),SLOT)


def test_rejects_conclusion_that_does_not_match_correct_option():
    with pytest.raises(ValueError,match="support the correct answer"):
        validate_generated_item(item("Step 1: Add the values. Step 2: Answer = 25."),SLOT)


def test_accepts_explicit_matching_option_conclusion():
    generated={**item("Review the premises carefully. Therefore, option C is correct."),**LOGICAL_SLOT}
    result=validate_generated_item(generated,LOGICAL_SLOT)
    assert result["explanation"].endswith("correct.")


def test_rejects_explicit_wrong_option_conclusion():
    generated={**item("Review the premises carefully. The correct option is D."),**LOGICAL_SLOT}
    with pytest.raises(ValueError,match="support the correct answer"):
        validate_generated_item(generated,LOGICAL_SLOT)


def test_rejects_repeated_recalculation():
    explanation="Step 1: Compute 20 from the values. Step 2: Compute 20 from the values. Step 3: Compute 20 from the values."
    with pytest.raises(ValueError,match="redundantly repeats"):
        validate_generated_item(item(explanation),SLOT)


def test_complete_option_text_starting_with_answer_letter_is_not_a_bare_key():
    generated={
        **LOGICAL_SLOT,
        "question":"Which structure removes the oldest inserted item first?",
        "options":{"A":"A tree","B":"A queue","C":"A stack","D":"A graph"},
        "correct_answer":"B",
        "explanation":"A queue follows first-in, first-out order. Answer = A queue.",
    }
    assert validate_generated_item(generated,LOGICAL_SLOT)["correct_answer"]=="B"


def test_rejects_quantitative_self_correction_and_option_guessing():
    explanation="Step 1: 35 / 12 = 2.92. Step 2: However, 2.92 is not among the options. Step 3: Answer = 25."
    with pytest.raises(ValueError):
        validate_generated_item(item(explanation),SLOT)


def test_rejects_quantitative_explanation_without_final_answer_step():
    with pytest.raises(ValueError,match="matching answer"):
        validate_generated_item(item("Step 1: 10 + 10 = 20. Step 2: The result is 20."),SLOT)


def test_rejects_final_numeric_answer_not_derived_by_prior_steps():
    explanation="Step 1: 945 / 8 = 118.125. Step 2: The quotient remains 118.125. Step 3: Answer = 20."
    with pytest.raises(ValueError,match="derive"):
        validate_generated_item(item(explanation),SLOT)


def test_generation_retries_invalid_explanation_and_accumulates_usage(monkeypatch):
    calls=[]
    responses=[
        ({"questions":[item("Step 1: Add the values. Step 2: Answer = 25.")]},{"input_tokens":10,"output_tokens":5,"total_tokens":15}),
        ({"questions":[item()]},{"input_tokens":12,"output_tokens":7,"total_tokens":19}),
    ]

    def fake_completion(system,prompt,temperature,**_kwargs):
        calls.append((system,prompt,temperature))
        return responses.pop(0)

    monkeypatch.setattr(test_generation,"json_completion",fake_completion)
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions,model,usage=test_generation.generate_questions([SLOT])

    assert len(calls)==2
    assert calls[0][2]==0
    assert "Do not think out loud" in calls[0][1]
    assert "must exactly match" in calls[0][1]
    assert "Never mention" in calls[0][1]
    assert "recent typed number patterns" in calls[0][1]
    assert "RETRY CORRECTION" in calls[1][1]
    assert "does not support the correct answer" in calls[1][1]
    assert questions[0]["correct_answer"]=="C"
    assert model=="test-model"
    assert usage["input_tokens"]==22
    assert usage["output_tokens"]==12
    assert usage["total_tokens"]==34


@pytest.mark.parametrize(
    "payload",
    [
        lambda generated:{"question":generated},
        lambda generated:{"questions":generated},
        lambda generated:generated,
    ],
    ids=["singular-question-wrapper","object-under-questions","bare-question"],
)
def test_single_question_generation_accepts_common_json_wrappers(monkeypatch,payload):
    generated=item()
    monkeypatch.setattr(
        test_generation,
        "json_completion",
        lambda *_args,**_kwargs:(payload(generated),{"input_tokens":2,"output_tokens":3,"total_tokens":5}),
    )
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions,model,usage=test_generation.generate_questions([SLOT],max_validation_attempts=1)

    assert len(questions)==1
    assert questions[0]["question"]==generated["question"]
    assert model=="test-model"
    assert usage["total_tokens"]==5


def test_multi_question_generation_still_requires_questions_array(monkeypatch):
    monkeypatch.setattr(
        test_generation,
        "json_completion",
        lambda *_args,**_kwargs:({"question":item()},{"input_tokens":2,"output_tokens":3,"total_tokens":5}),
    )
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context(),pytest.raises(ValueError,match="expected 2 questions"):
        test_generation.generate_questions([SLOT,SLOT],max_validation_attempts=1)


def test_generation_uses_development_fixture_after_validation_is_exhausted(monkeypatch):
    invalid={"questions":[item("Step 1: Add the values. Step 2: Answer = 25.")]}
    monkeypatch.setattr(
        test_generation,
        "json_completion",
        lambda *_args,**_kwargs:(invalid,{"input_tokens":10,"output_tokens":5,"total_tokens":15}),
    )
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=True)
    with app.app_context():
        questions,model,usage=test_generation.generate_questions([SLOT])

    assert questions[0]["category"]==SLOT["category"]
    assert questions[0]["correct_answer"]=="B"
    assert model=="demo-fixture-fallback"
    assert usage["total_tokens"]==45


def test_generation_uses_development_fixture_when_provider_is_unavailable(monkeypatch):
    def unavailable(*_args,**_kwargs):
        raise test_generation.ProviderError("transient","provider timed out",True,503)

    monkeypatch.setattr(test_generation,"json_completion",unavailable)
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",
        QUESTION_GENERATION_MAX_COMPLETION_TOKENS=1536,
        OPENAI_BACKGROUND_TIMEOUT_SECONDS=20,OPENAI_TIMEOUT_SECONDS=6,
        ALLOW_DEMO_QUESTIONS=True,
    )
    with app.app_context():
        questions,model,usage=test_generation.generate_questions([SLOT])

    assert questions[0]["category"]==SLOT["category"]
    assert model=="demo-fixture-provider-fallback"
    assert usage["validation_attempt_count"]==1


def test_technical_generation_prompt_uses_selected_language(monkeypatch):
    prompts=[]
    generated={
        **TECHNICAL_SLOT,
        "question":"Which statement about Java variables is correct?",
        "options":{"A":"They have declared types","B":"They never have types","C":"They cannot store values","D":"They only store text"},
        "correct_answer":"A",
        "explanation":"Java variables use declared types, so option A is correct.",
    }

    def fake_completion(_system,prompt,_temperature,**_kwargs):
        prompts.append(prompt)
        return {"questions":[generated]},{"input_tokens":1,"output_tokens":1,"total_tokens":2}

    monkeypatch.setattr(test_generation,"json_completion",fake_completion)
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions,_model,_usage=test_generation.generate_questions([TECHNICAL_SLOT])

    assert questions[0]["category"]=="Technical Aptitude"
    assert '"technical_language":"Java"' in prompts[0]
    assert "use exactly that selected language" in prompts[0]


def test_batch_schema_requires_exact_question_count():
    schema=test_generation._batch_response_schema([SLOT for _ in range(21)])
    questions=schema["properties"]["questions"]
    assert questions["minItems"]==21
    assert questions["maxItems"]==21
    assert questions["items"]["additionalProperties"] is False
    assert questions["items"]["required"]==[
        "question","correct_option","distractors","reason","calculation_step_1","calculation_step_2",
        "question_code","correct_option_code","distractor_codes","category","topic","difficulty",
    ]


def test_batch_item_builds_answer_and_explanation_from_one_correct_option():
    generated={
        "question":"What is 12 plus 8?","correct_option":"20","distractors":["18","19","21"],
        "reason":"","calculation_step_1":"12 + 8 = 20","calculation_step_2":"The calculated value is 20",
        "question_code":None,"correct_option_code":None,"distractor_codes":[None,None,None],
    }
    canonical=test_generation._canonicalize_batch_item(generated,SLOT)
    assert canonical["options"][canonical["correct_answer"]]=="20"
    assert canonical["explanation"].endswith("Answer = 20.")
    assert validate_generated_item({**canonical,**SLOT},SLOT)["correct_answer"]==canonical["correct_answer"]


@pytest.mark.parametrize("field",["question","explanation","A"])
def test_rejects_internal_prompt_tokens_in_all_public_fields(field):
    generated=item()
    if field=="A":generated["options"]={**generated["options"],"A":"scenario_seed 9698bbf0"}
    else:generated[field]=f"Valid content that exposes scenario_seed 9698bbf0 in the {field}."
    with pytest.raises(ValueError,match="internal prompt token"):
        validate_generated_item(generated,SLOT)


def test_rejects_seed_value_even_without_internal_field_name():
    generated=item();generated["question"]="What average follows from private value 9698bbf0 in this example?"
    with pytest.raises(ValueError,match="internal seed value"):
        validate_generated_item(generated,SLOT,internal_values=("9698bbf0",))


def test_structural_hash_matches_reworded_numeric_scenario_with_same_topic():
    first="A bakery sold 180, 195, and 210 loaves on three days. Find the average."
    second="Daily sales were 210, 180, and 195 units. What was the mean?"
    assert structural_hash(first,"Quantitative Aptitude","Average")==structural_hash(second,"Quantitative Aptitude","Average")


def test_structural_hash_does_not_merge_unrelated_topic_or_number_sets():
    base="Records contain 180, 195, and 210 entries."
    same_numbers_other_topic="A series contains 180, 195, and 210."
    overlapping_numbers="Records contain 180, 195, and 225 entries."
    signature=structural_hash(base,"Computer Fundamentals","Database Basics")
    assert signature!=structural_hash(same_numbers_other_topic,"Logical Reasoning","Number Series")
    assert signature!=structural_hash(overlapping_numbers,"Computer Fundamentals","Database Basics")
    assert structural_hash("A system has 10 records.","Computer Fundamentals","Database Basics") is None


def test_numeric_pattern_preserves_number_types_and_multiplicity():
    assert numeric_pattern("An item costs ₹800 after a 15% discount from 800 units.")==["number:800","number:800","percent:15"]


def test_generation_retries_structurally_duplicate_batch(monkeypatch):
    slots=[LOGICAL_SLOT,LOGICAL_SLOT]
    first={**LOGICAL_SLOT,"question":"A code uses the values 180, 195, and 210. Which statement follows?","options":{"A":"First","B":"Second","C":"Third","D":"Fourth"},"correct_answer":"A","explanation":"The stated rule shows that the correct option is A."}
    duplicate={**first,"question":"Values 210, 180, and 195 appear in another story. Which statement follows?"}
    replacement={**first,"question":"Every manager reviews reports, and Kiran is a manager. Which conclusion must hold?"}
    responses=[
        ({"questions":[first,duplicate]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}),
        ({"questions":[first,replacement]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}),
    ]
    calls=[]

    def fake_completion(*args,**_kwargs):
        calls.append(args)
        return responses.pop(0)

    monkeypatch.setattr(test_generation,"json_completion",fake_completion)
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions,_model,usage=test_generation.generate_questions(slots)

    assert len(calls)==2
    assert questions[0]["structural_hash"]!=questions[1]["structural_hash"]
    assert usage["total_tokens"]==60
