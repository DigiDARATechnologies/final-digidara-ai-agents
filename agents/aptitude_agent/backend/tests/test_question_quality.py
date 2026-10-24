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


def test_rejects_a_provider_item_for_the_wrong_slot():
    generated={**item(),"topic":"Profit & Loss"}
    with pytest.raises(ValueError,match="does not match the requested slot"):
        validate_generated_item(generated,SLOT)


def test_rejects_slot_based_technical_placeholder_question():
    slot = {
        "category": "Technical Aptitude",
        "topic": "Machine Learning Fundamentals",
        "difficulty": "Easy",
        "technical_skill": "Machine Learning",
    }
    generated = {
        **slot,
        "question": "Consider a new python assessment dataset for Machine Learning Fundamentals in slot 5. Which statement best applies to Machine Learning Fundamentals here?",
        "options": {
            "A": "The stated concept applies",
            "B": "It is unrelated",
            "C": "It is never used",
            "D": "No conclusion follows",
        },
        "correct_answer": "A",
        "explanation": "The Machine Learning concept in this slot is represented by the stated correct option.",
    }
    with pytest.raises(ValueError, match="placeholder"):
        validate_generated_item(generated, slot)


def test_rejects_equivalent_numeric_distractors():
    generated=item()
    generated["options"]={"A":"10","B":"15","C":"20","D":"20.0"}
    with pytest.raises(ValueError,match="unique"):
        validate_generated_item(generated,SLOT)


def test_rejects_an_incorrect_key_for_an_explicit_arithmetic_stem():
    generated={
        **SLOT,
        "question":"What is 12 plus 8?",
        "options":{"A":"18","B":"19","C":"20","D":"21"},
        "correct_answer":"A",
        "explanation":"Step 1: 12 + 8 = 20. Step 2: The result is 20. Step 3: Answer = 18.",
    }
    with pytest.raises(ValueError,match="calculable question result"):
        validate_generated_item(generated,SLOT)


def test_rejects_an_explicit_arithmetic_stem_with_no_correct_option():
    generated={
        **SLOT,
        "question":"What is 12 plus 8?",
        "options":{"A":"17","B":"18","C":"19","D":"21"},
        "correct_answer":"A",
        "explanation":"Step 1: 12 + 8 = 20. Step 2: The result is 20. Step 3: Answer = 17.",
    }
    with pytest.raises(ValueError,match="no option"):
        validate_generated_item(generated,SLOT)


def test_rejects_an_incomplete_question_stem():
    generated={**item(),"question":"Choose the answer."}
    with pytest.raises(ValueError,match="incomplete"):
        validate_generated_item(generated,SLOT)


@pytest.mark.parametrize(
    ("slot", "question", "options", "answer", "explanation", "reason"),
    [
        (
            {"category":"Computer Fundamentals","topic":"Database Basics","difficulty":"Easy"},
            "Which of the following is a method to improve database query performance?",
            {"A":"Normalization","B":"Denormalization","C":"Indexing","D":"Partitioning"},
            "C", "Indexing can improve lookup performance by using a search structure. Answer = Indexing.",
            "database-performance",
        ),
        (
            {"category":"Computer Fundamentals","topic":"Database Basics","difficulty":"Easy"},
            "Which database query is faster?",
            {"A":"Query A","B":"Query B","C":"Both are identical","D":"Not enough information"},
            "A", "The database, data distribution, and execution conditions are not specified. Answer = Query A.",
            "database-speed",
        ),
        (
            {"category":"Logical Reasoning","topic":"Ranking & Ordering","difficulty":"Easy"},
            "Alice is first, Bob second, and Charlie third. If Charlie beats Bob, what will be their new ranks?",
            {"A":"Alice first, Charlie second, Bob third","B":"Charlie first, Alice second, Bob third","C":"Bob first, Alice second, Charlie third","D":"Alice first, Bob second, Charlie third"},
            "A", "The result is uncertain because the stem does not say whether Charlie passes Alice. Answer = Alice first, Charlie second, Bob third.",
            "ranking-assumption",
        ),
        (
            {"category":"Computer Fundamentals","topic":"Cloud Architecture","difficulty":"Medium"},
            "What is the primary benefit of using cloud architecture?",
            {"A":"Scalability","B":"Cost reduction","C":"Data security","D":"Speed"},
            "A", "The broad wording does not define a use case that makes scalability primary. Answer = Scalability.",
            "cloud-context",
        ),
        (
            {"category":"Technical Aptitude","topic":"Hashing","difficulty":"Medium","technical_language":"Python"},
            "What is the time complexity of accessing an element in a hash table?",
            {"A":"O(1)","B":"O(n)","C":"O(log n)","D":"O(n log n)"},
            "A", "Hash lookup is O(1) on average but can be O(n) in the worst case. Answer = O(1).",
            "hash-assumption",
        ),
        (
            {"category":"Quantitative Aptitude","topic":"Combinations","difficulty":"Medium"},
            "Five computers can communicate with every other computer. How many unique connections can be formed?",
            {"A":"5","B":"10","C":"15","D":"20"},
            "B", "The connection model is not specified, so directed and undirected interpretations differ. Answer = 10.",
            "connection-assumption",
        ),
        (
            {"category":"Technical Aptitude","topic":"Graph Algorithms","difficulty":"Medium","technical_language":"Python"},
            "How many edges are there in a graph with four vertices?",
            {"A":"3","B":"4","C":"6","D":"12"},
            "C", "The graph structure is not specified, so the edge count is not unique. Answer = 6.",
            "graph-structure",
        ),
        (
            {"category":"Verbal Ability","topic":"Spelling","difficulty":"Easy"},
            "Identify the misspelled word.",
            {"A":"Recieve","B":"Receeve","C":"Receive","D":"Recive"},
            "C", "Receive is correctly spelled, so it cannot be the misspelled word. Answer = Receive.",
            "spelling-polarity",
        ),
    ],
)
def test_rejects_ambiguous_or_unsupported_single_answer_items(slot, question, options, answer, explanation, reason):
    generated={**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation}
    with pytest.raises(ValueError):
        validate_generated_item(generated,slot)


def test_accepts_explicit_assumptions_for_context_sensitive_questions():
    slot={"category":"Computer Fundamentals","topic":"Cloud Architecture","difficulty":"Medium"}
    generated={
        **slot,
        "question":"When demand changes throughout the day, what primary cloud benefit lets a service adjust resources?",
        "options":{"A":"Scalability","B":"A fixed hardware layout","C":"Manual backups","D":"Offline access"},
        "correct_answer":"A",
        "explanation":"Scalability lets resources expand or shrink with changing demand. Answer = Scalability.",
    }
    assert validate_generated_item(generated,slot)["correct_answer"]=="A"


@pytest.mark.parametrize(
    "slot,question,options,answer,explanation",
    [
        (
            {"category":"Computer Fundamentals","topic":"Database Basics","difficulty":"Easy"},
            "Given an index on users.email, which database query is faster for an exact email lookup?",
            {"A":"The indexed email lookup","B":"A full table scan","C":"A random update","D":"A table drop"},
            "A", "The index narrows the exact lookup to matching records instead of scanning every row. Answer = The indexed email lookup.",
        ),
        (
            {"category":"Logical Reasoning","topic":"Ranking & Ordering","difficulty":"Easy"},
            "Alice is third and Bob is fifth; if Alice overtakes Bob without passing anyone else, what is Alice's new position?",
            {"A":"Third","B":"Fourth","C":"Fifth","D":"Sixth"},
            "C", "Alice moves into Bob's fifth position when she overtakes him without passing anyone else. Answer = Fifth.",
        ),
        (
            {"category":"Technical Aptitude","topic":"Hashing","difficulty":"Medium","technical_language":"Python"},
            "What is the average-case time complexity of searching in a hash table with a well-distributed hash function?",
            {"A":"O(1)","B":"O(log n)","C":"O(n)","D":"O(n log n)"},
            "A", "A well-distributed hash function usually locates a key in constant average time. Answer = O(1).",
        ),
        (
            {"category":"Technical Aptitude","topic":"Graph Algorithms","difficulty":"Medium","technical_language":"Python"},
            "How many edges does a complete undirected graph with four vertices have?",
            {"A":"3","B":"4","C":"6","D":"12"},
            "C", "Each pair of four vertices forms one edge, giving 4 times 3 divided by 2, or 6. Answer = 6.",
        ),
    ],
)
def test_accepts_clear_controls_for_context_sensitive_questions(slot,question,options,answer,explanation):
    generated={**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation}
    assert validate_generated_item(generated,slot)["correct_answer"]==answer


def test_rejects_sql_content_mapped_to_graph_topic():
    slot={"category":"Technical Aptitude","topic":"Graph Algorithms","difficulty":"Medium","technical_language":"SQL"}
    generated={
        **slot,
        "question":"Which SQL query retrieves rows from a customers table?",
        "options":{"A":"SELECT * FROM customers","B":"BFS(customers)","C":"sort(customers)","D":"hash(customers)"},
        "correct_answer":"A",
        "explanation":"The SELECT statement retrieves rows from the named table. Answer = SELECT * FROM customers.",
    }
    with pytest.raises(ValueError,match="content does not match"):
        validate_generated_item(generated,slot)


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


def test_accepts_a_final_step_narrated_in_words_instead_of_repeating_the_digits():
    # Production failure: 20% of 250 is spelled out, but the final subtraction
    # is only narrated ("Subtract 50 from 250"), never repeating "200" before
    # the answer line. That is still a real, correct derivation.
    generated=item("Step 1: Find 20% of 250 = 50. Step 2: Subtract 50 from 250. Answer = 200.")
    generated["options"]={"A":"150","B":"180","C":"200","D":"250"}
    assert validate_generated_item(generated,SLOT)["correct_answer"]=="C"


def test_accepts_imperative_arithmetic_phrasing_in_the_final_step():
    generated=item("Step 1: The two prices are 120 and 30. Step 2: Add 120 to 30. Answer = 150.")
    generated["options"]={"A":"90","B":"120","C":"150","D":"180"}
    assert validate_generated_item(generated,SLOT)["correct_answer"]=="C"

    generated=item("Step 1: Start with 200 units. Step 2: Divide 200 by 4. Answer = 50.")
    generated["options"]={"A":"25","B":"40","C":"50","D":"80"}
    assert validate_generated_item(generated,SLOT)["correct_answer"]=="C"


def test_still_rejects_an_unrelated_calculation_narrated_in_words():
    # An explanation that narrates *some* arithmetic, but not the one that
    # reaches the stated option, must still be rejected -- the fix must not
    # accept an explanation just because it contains any calculation at all.
    explanation="Step 1: Find 20% of 250 = 50. Step 2: Subtract 10 from 90. Answer = 200."
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
    assert "self-check every item in this same response" in calls[0][1]
    assert "Copy each slot's category, topic, and difficulty exactly" in calls[0][1]
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
    assert "using exactly the slot's selected technical_language" in prompts[0]


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


ANALYTICAL_SLOT={"category":"Analytical Reasoning","topic":"Advanced Caselets","difficulty":"Medium"}


def caselet(reason="",step_1="",step_2=""):
    return {
        "question":"A company has 200 employees and 60% of them are men. How many men work there?",
        "correct_option":"120","distractors":["80","100","140"],
        "reason":reason,"calculation_step_1":step_1,"calculation_step_2":step_2,
        "question_code":None,"correct_option_code":None,"distractor_codes":[None,None,None],
    }


def test_numeric_caselet_uses_calculation_steps_when_reason_is_empty():
    # Production 2026-10-23: the model put a caselet's working in the
    # calculation fields, the explanation became only "Answer = 120." and
    # whole tests failed after every retry.
    canonical=test_generation._canonicalize_batch_item(caselet(step_1="60% of 200 = 120"),ANALYTICAL_SLOT)
    assert canonical["explanation"]=="60% of 200 = 120. Answer = 120."
    assert validate_generated_item({**canonical,**ANALYTICAL_SLOT},ANALYTICAL_SLOT)["correct_answer"]==canonical["correct_answer"]


def test_non_quantitative_answer_with_no_reasoning_is_still_rejected():
    canonical=test_generation._canonicalize_batch_item(caselet(),ANALYTICAL_SLOT)
    assert canonical["explanation"]==" Answer = 120."
    with pytest.raises(ValueError,match="explanation must explain"):
        validate_generated_item({**canonical,**ANALYTICAL_SLOT},ANALYTICAL_SLOT)


def test_restating_the_answer_as_an_equation_is_not_a_calculation():
    canonical=test_generation._canonicalize_batch_item(caselet(reason="Men = 120"),ANALYTICAL_SLOT)
    with pytest.raises(ValueError,match="explanation must explain"):
        validate_generated_item({**canonical,**ANALYTICAL_SLOT},ANALYTICAL_SLOT)


def test_generation_prompt_asks_for_reason_on_numeric_analytical_items():
    prompt=test_generation._batch_prompt([],[],[],"batch")
    assert "including Analytical Reasoning caselets" in prompt

@pytest.mark.parametrize("distractors", [["20", "19", "21"], ["20.0", "", "21"]])
def test_batch_item_rejects_empty_or_normalized_duplicate_options(distractors):
    generated={
        "question":"What is 12 plus 8?","correct_option":"20","distractors":distractors,
        "reason":"","calculation_step_1":"12 + 8 = 20","calculation_step_2":"The calculated value is 20",
        "question_code":None,"correct_option_code":None,"distractor_codes":[None,None,None],
    }
    with pytest.raises(ValueError, match="distinct and non-empty"):
        test_generation._canonicalize_batch_item(generated,SLOT)


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
        ({"questions":[replacement]},{"input_tokens":20,"output_tokens":10,"total_tokens":30}),  # only the duplicate slot is re-asked
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


def test_a_rejected_item_logs_its_actual_content_not_just_the_static_message(monkeypatch,caplog):
    # validate_generated_item's error text is a fixed string shared by several
    # different checks, so it alone can't diagnose a recurrence in production
    # (see the live "structured explanation must derive..." 503s). The batch
    # loop must log the real explanation/options once, so the *next*
    # occurrence is diagnosable from one log pull instead of a guessing loop.
    bad_explanation="Step 1: This looks tricky. Step 2: Going with intuition. Answer = 42."
    bad_item={**SLOT,"question":"What is the value described in this scenario?","options":{"A":"10","B":"20","C":"42","D":"50"},"correct_answer":"C","explanation":bad_explanation}
    response=({"questions":[bad_item]},{"input_tokens":10,"output_tokens":5,"total_tokens":15})
    monkeypatch.setattr(test_generation,"json_completion",lambda *a,**k:response)
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key",OPENAI_MODEL="test-model",ALLOW_DEMO_QUESTIONS=False)
    with app.app_context(), pytest.raises(Exception):
        test_generation.generate_questions([SLOT],max_validation_attempts=1)
    logged=" ".join(record.getMessage() for record in caplog.records if "Question validation failed" in record.getMessage())
    assert bad_explanation in logged
    assert "42" in logged and "Quantitative Aptitude" in logged


QUANT_TOPICS=[item["name"] for item in test_generation.topic_definitions_for("Quantitative Aptitude")]


def rescue_slots(count=4):
    return [{**SLOT,"topic":QUANT_TOPICS[index]} for index in range(count)]


def test_swapped_topics_stay_in_the_category_and_avoid_topics_already_in_the_test():
    slots=rescue_slots()
    swapped=test_generation._swap_topics([slots[1]],[slot["topic"] for slot in slots])
    assert swapped[0]["category"]=="Quantitative Aptitude"
    assert swapped[0]["topic"] in QUANT_TOPICS
    assert swapped[0]["topic"] not in {slot["topic"] for slot in slots}
    assert swapped[0]["difficulty"]==slots[1]["difficulty"]


def test_one_slot_that_fails_every_attempt_is_rescued_on_another_topic(monkeypatch):
    # Production: one stubborn question ("calculation does not derive correct
    # option") failed the whole 30-question test after every retry.
    slots=rescue_slots()
    accepted={0:{"question":"q0"},2:{"question":"q2"},3:{"question":"q3"}}
    seen={}

    def fake_generate(rescue,**kwargs):
        seen.update(slots=rescue,**kwargs)
        return [{"question":"rescued","topic":rescue[0]["topic"]}],"test-model",{"total_tokens":7}

    monkeypatch.setattr(test_generation,"generate_questions",fake_generate)
    app=Flask(__name__)
    with app.app_context():
        result=test_generation._rescue_failed_slots(
            slots,accepted,ValueError("quantitative calculation does not derive correct option"),True,
            avoid_questions=["old"],avoid_number_patterns=None,deadline=None,background=False,request_timeout=None,
        )
    assert result==({"total_tokens":7},"test-model")
    assert accepted[1]["question"]=="rescued"
    assert seen["slots"][0]["topic"]!=slots[1]["topic"]
    assert seen["_rescue"] is False  # never recurses twice
    assert set(seen["avoid_questions"])=={"old","q0","q2","q3"}


@pytest.mark.parametrize("accepted,enabled",[
    ({0:{"question":"q0"},3:{"question":"q3"}},True),   # half the test failed: a real problem, not one topic
    ({},True),                                          # nothing valid at all
    ({0:{"question":"q0"},2:{"question":"q2"},3:{"question":"q3"}},False),  # already a rescue
])
def test_rescue_is_only_for_a_few_slots_once(monkeypatch,accepted,enabled):
    monkeypatch.setattr(test_generation,"generate_questions",lambda *a,**k: pytest.fail("must not generate"))
    app=Flask(__name__)
    with app.app_context():
        assert test_generation._rescue_failed_slots(
            rescue_slots(),dict(accepted),ValueError("x"),enabled,
            avoid_questions=[],avoid_number_patterns=None,deadline=None,background=False,request_timeout=None,
        ) is None


def test_a_failed_rescue_leaves_the_original_failure(monkeypatch):
    def failing(*_args,**_kwargs):
        raise ValueError("still invalid")
    monkeypatch.setattr(test_generation,"generate_questions",failing)
    accepted={0:{"question":"q0"},2:{"question":"q2"},3:{"question":"q3"}}
    app=Flask(__name__)
    with app.app_context():
        assert test_generation._rescue_failed_slots(
            rescue_slots(),accepted,ValueError("x"),True,
            avoid_questions=[],avoid_number_patterns=None,deadline=None,background=False,request_timeout=None,
        ) is None
    assert 1 not in accepted

@pytest.mark.parametrize("skill,topic,needle", [
    ("Python", "Programming Fundamentals", "python"),
    ("Machine Learning", "Machine Learning Fundamentals", "machine learning"),
    ("SQL", "SQL Queries & Joins", "sql"),
    ("Power BI", "Power BI & Data Visualization", "power bi"),
])
def test_saved_skill_fallback_is_topic_specific(skill, topic, needle):
    slot = {
        "category": "Technical Aptitude", "topic": topic, "difficulty": "Easy",
        "technical_skill": skill, "technical_role_terms": (skill.casefold(),),
    }
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert needle in " ".join((validated["question"], validated["explanation"])).casefold()


def test_quantitative_fallback_is_arithmetically_validated():
    slot = {"category": "Quantitative Aptitude", "topic": "Simplification", "difficulty": "Easy"}
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert validated["correct_answer"] == "A"
    assert "Step 1:" in validated["explanation"]


def test_decision_table_fallback_is_topic_specific():
    slot = {"category": "Analytical Reasoning", "topic": "Decision Tables", "difficulty": "Easy"}
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert "decision table" in f"{validated['question']} {validated['explanation']}".casefold()


def test_contextual_cloze_fallback_is_a_real_question():
    slot = {"category": "Verbal Ability", "topic": "Contextual Cloze Tests", "difficulty": "Easy"}
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert validated["question"].endswith("?")
    assert "completes the sentence" in validated["question"].casefold()


@pytest.mark.parametrize("skill,topic,needle", [
    ("React", "React Fundamentals", "react"),
    ("Flask", "Flask Web Development", "flask"),
])
def test_saved_frontend_backend_skill_fallbacks_are_concrete(skill, topic, needle):
    slot = {"category": "Technical Aptitude", "topic": topic, "difficulty": "Easy",
            "technical_skill": skill}
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert needle in f"{validated['question']} {validated['explanation']}".casefold()


def test_excel_skill_fallback_is_concrete():
    slot = {"category": "Technical Aptitude", "topic": "Excel Data Analysis", "difficulty": "Easy",
            "technical_skill": "Excel"}
    question, options, answer, explanation = test_generation._meaningful_demo_item(slot)
    validated = validate_generated_item(
        {**slot, "question": question, "options": options,
         "correct_answer": answer, "explanation": explanation}, slot,
    )
    assert "excel" in f"{validated['question']} {validated['explanation']}".casefold()
