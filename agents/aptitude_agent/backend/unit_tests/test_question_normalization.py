import pytest
from flask import Flask

from backend.app.services.question_validation import _validate_assumptions_and_scope, content_hash, normalize_question_text, questions_are_near_duplicates, validate_generated_item
from backend.app.services.test_generation import build_category_slots, demo_questions


@pytest.mark.parametrize("first,second",[
    ("What is RAM?", "WHAT IS RAM?"),
    ("What is RAM?", "What   is   RAM?"),
    ("What is RAM?", "What is RAM"),
    ("Which OS component manages CPU scheduling? (Local practice abc123)", "Which OS component manages CPU scheduling? (Local practice xyz999)"),
])
def test_normalized_question_fingerprint_rejects_surface_variations(first,second):
    assert content_hash(first)==content_hash(second)
    assert questions_are_near_duplicates(first,second)


def test_near_duplicate_concept_is_rejected():
    assert questions_are_near_duplicates(
        "What is the purpose of RAM?",
        "What function does RAM perform in a computer?",
    )


def test_meaningfully_different_questions_remain_distinct():
    assert not questions_are_near_duplicates(
        "Which protocol automatically assigns IP addresses on a network?",
        "What is the main purpose of a database index?",
    )


def test_topic_alignment_rejects_oop_question_labeled_as_loops():
    with pytest.raises(ValueError, match="does not match"):
        _validate_assumptions_and_scope(
            "Which principle hides an object's internal state from callers?",
            {"A": "Encapsulation", "B": "Iteration", "C": "Sorting", "D": "Indexing"},
            "Technical Aptitude", "Loops",
        )


def test_topic_alignment_rejects_testing_question_labeled_as_variables():
    with pytest.raises(ValueError, match="does not match"):
        _validate_assumptions_and_scope(
            "Which practice checks a function in isolation with assertions?",
            {"A": "Unit testing", "B": "Variable assignment", "C": "Looping", "D": "Sorting"},
            "Technical Aptitude", "Variables & Data Types",
        )


def test_saved_skill_alignment_rejects_generic_question_with_skill_label():
    slot = {"category": "Technical Aptitude", "topic": "Programming Fundamentals", "difficulty": "Easy", "technical_skill": "Machine Learning"}
    item = {**slot, "question": "What does a function parameter provide?", "options": {"A": "Input", "B": "Output", "C": "A table", "D": "A file"}, "correct_answer": "A", "explanation": "A parameter provides input to a function."}
    with pytest.raises(ValueError, match="saved technical skill"):
        validate_generated_item(item, slot)


def test_saved_skill_alignment_rejects_power_bi_question_in_machine_learning_slot():
    slot = {"category": "Technical Aptitude", "topic": "Machine Learning Fundamentals", "difficulty": "Easy", "technical_skill": "Machine Learning", "technical_role_terms": ("python", "machine learning", "sql", "power bi")}
    item = {**slot, "question": "Which Power BI visualization best compares categories?", "options": {"A": "Bar chart", "B": "Slicer", "C": "Measure", "D": "Card"}, "correct_answer": "A", "explanation": "Machine learning is unrelated here; a bar chart is a Power BI visualization for comparing categories."}
    with pytest.raises(ValueError, match="does not match"):
        validate_generated_item(item, slot)


@pytest.mark.parametrize("category",[
    "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability",
    "Analytical Reasoning", "Computer Fundamentals", "Technical Aptitude",
])
def test_local_category_fixture_produces_five_unique_sample_questions(category):
    app=Flask(__name__)
    with app.app_context():
        # The handcrafted demo fixture is a five-item validation sample. The
        # learner-facing Category Practice route uses live generation and does
        # not enable this local fallback.
        questions=demo_questions(build_category_slots(category,"Beginner")[:5])
    fingerprints=[content_hash(question["question"]) for question in questions]
    assert len(questions)==5
    assert len(fingerprints)==len(set(fingerprints))
    assert all("local practice" not in question["question"].casefold() for question in questions)


@pytest.mark.parametrize("topics",[
    # Random draws that used to fail: reworded fixtures stayed near duplicates.
    ["File Systems", "Network Topologies & Hardware Devices", "Computer Basics", "Software Types", "Cloud Computing Basics"],
    ["Computer Organization", "System Security", "Advanced OSI vs TCP/IP Models", "IP Addressing", "Advanced Networking"],
    ["CPU Scheduling Algorithms", "OSI vs TCP/IP Models", "Internet Basics", "Concurrency & Deadlocks", "Computer Basics"],
])
def test_alike_topics_still_get_five_different_sample_questions(topics):
    app=Flask(__name__)
    with app.app_context():
        questions=demo_questions(build_category_slots("Computer Fundamentals","Beginner",topics=topics)[:5])
    texts=[question["question"] for question in questions]
    assert len(texts)==5
    assert not any(questions_are_near_duplicates(first,second) for index,first in enumerate(texts) for second in texts[index+1:])


def test_a_question_needs_the_passage_or_data_it_refers_to():
    import pytest
    from backend.app.services.question_validation import missing_material

    for question in (
        "What tone does the author use in the passage?",
        "What is the main idea of the passage about climate change?",
        "In the passage, the author emphasizes teamwork. What is the main idea?",
        "Using the following table, which company grew fastest?",
    ):
        assert missing_material(question), question
    for question in (
        "Read the following passage: 'The cat sat on the mat. It was a sunny day.' What is the main idea?",
        "Identify the tone of the following passage: 'The sun set behind the mountains, casting a golden hue.'",
        "From the following table: Company A sold 120 units in Jan, 150 in Feb. Which grew?",
        "If 'CAT' is coded as '3120', what is the code for 'DOG'?",
        "Which of the following sentences uses the article correctly?",
        "In a pie chart, if 40% of the chart represents sales, what is the angle?",
    ):
        assert not missing_material(question), question
