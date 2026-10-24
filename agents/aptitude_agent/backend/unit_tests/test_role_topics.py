from backend.app.services.role_topics import GENERIC_TECHNICAL_TOPICS, normalize_technical_skills, role_skill_topics_for_level, role_technical_context, role_topics_for_category, role_topics_for_level
from backend.app.services.test_generation import _meaningful_demo_item, build_category_slots, build_slots
from backend.app.services.question_validation import validate_generated_item
from backend.app.services.topic_selection_service import select_mixed_topics_for_attempt


def test_role_context_maps_common_roles_without_changing_category_taxonomy():
    assert role_technical_context("Python Developer")["family"] == "python"
    assert role_technical_context("MERN Stack Developer")["family"] == "mern"
    assert role_technical_context(".NET Developer")["family"] == "dotnet"
    assert role_technical_context("Data Analyst", ["SQL"])["family"] == "data"


def test_role_topic_pools_use_existing_technical_topic_labels():
    for role in ("Python Developer", "MERN Stack Developer", ".NET Developer", "Data Analyst", "DevOps Engineer"):
        topics = set(role_topics_for_category(role, []))
        assert topics
        assert set(topics) <= set(role_topics_for_level(role, [], "Beginner") + role_topics_for_level(role, [], "Intermediate") + role_topics_for_level(role, [], "Advanced"))


def test_category_and_mixed_slots_carry_role_context():
    category = build_category_slots("Technical Aptitude", "Beginner", technical_role="MERN Stack Developer")
    mixed = build_slots(category_counts={"Technical Aptitude": 3}, technical_role="Data Analyst", technical_skills=["SQL"])
    assert all(slot["technical_role"] == "MERN Stack Developer" for slot in category)
    assert all(slot["technical_role_family"] == "data" for slot in mixed)
    assert all("technical_role_terms" in slot for slot in mixed)


def test_missing_role_uses_generic_topics_and_common_categories_are_unchanged():
    context = role_technical_context(None, [])
    assert context['family'] == 'generic'
    assert context['language'] is None
    assert set(role_topics_for_category(None, [])) <= set(GENERIC_TECHNICAL_TOPICS)
    generic = build_category_slots('Technical Aptitude', 'Beginner', technical_role='Unclear professional')
    assert all('technical_language' not in slot for slot in generic)
    common = build_slots(category_counts={'Logical Reasoning': 2}, technical_role='DevOps Engineer')
    assert all('technical_role' not in slot for slot in common)


def test_saved_skills_are_carried_into_role_context_without_legacy_language_selection():
    context = role_technical_context('Full Stack Developer', ['Python', 'SQL', 'React'])
    assert context['family'] == 'mern'
    assert {'python', 'sql', 'react'} <= set(context['terms'])
    skill_driven = build_category_slots(
        'Technical Aptitude', 'Beginner', technical_role='Unclear role', technical_skills=['Python', 'SQL']
    )[0]
    assert skill_driven['technical_role_family'] == 'python'


def test_deterministic_technical_fallback_is_meaningful_and_validated():
    slot = {'category': 'Technical Aptitude', 'topic': 'Functions', 'difficulty': 'Easy'}
    question, options, answer, explanation = _meaningful_demo_item(slot)
    validated = validate_generated_item({**slot, 'question': question, 'options': options,
                                         'correct_answer': answer, 'explanation': explanation}, slot)
    assert 'assigned topic' not in validated['question'].casefold()
    assert 'Practice item' not in validated['question']


def test_mixed_technical_slice_starts_with_distinct_saved_skill_topics():
    topics = role_skill_topics_for_level(
        "Software Engineer", ["Python", "SQL", "React", "Git", "Testing"], "Beginner"
    )
    assert len(topics) == 5
    assert len({topic.casefold() for topic in topics}) == 5


def test_data_analyst_saved_skills_drive_the_entire_topic_pool():
    topics = role_topics_for_level(
        "Data Analyst", ["Python", "Machine Learning", "SQL", "Power BI"], "Beginner"
    )
    assert topics[:4] == (
        "Programming Fundamentals", "Machine Learning Fundamentals",
        "SQL Queries & Joins", "Power BI & Data Visualization",
    )
    assert set(topics) == set(topics[:4])


def test_saved_skill_aliases_are_canonicalized_for_topic_planning():
    assert normalize_technical_skills(["python", "SQL", "ml", "powerbi"]) == [
        "Python", "SQL", "Machine Learning", "Power BI"
    ]
    assert role_skill_topics_for_level(
        "Data Scientist", ["python", "sql", "ml", "powerbi"], "Beginner"
    ) == (
        "Programming Fundamentals", "SQL Queries & Joins",
        "Machine Learning Fundamentals", "Power BI & Data Visualization",
    )


def test_react_and_flask_saved_skills_get_dedicated_topics():
    topics = role_skill_topics_for_level(
        "Data Analyst", ["Python", "SQL", "React", "Flask"], "Beginner"
    )
    assert topics == (
        "Programming Fundamentals", "SQL Queries & Joins",
        "React Fundamentals", "Flask Web Development",
    )
    slots = build_category_slots(
        "Technical Aptitude", "Beginner", technical_role="Data Analyst",
        technical_skills=["Python", "SQL", "React", "Flask"],
    )
    assert [slot["technical_skill"] for slot in slots[:4]] == ["Python", "SQL", "React", "Flask"]


def test_excel_saved_skill_gets_a_dedicated_topic():
    topics = role_skill_topics_for_level(
        "Data Analyst", ["Python", "SQL", "Excel", "Power BI"], "Beginner"
    )
    assert "Excel Data Analysis" in topics
    slots = build_category_slots(
        "Technical Aptitude", "Beginner", technical_role="Data Analyst",
        technical_skills=["Python", "SQL", "Excel", "Power BI"],
    )
    assert {slot["technical_skill"] for slot in slots[:4]} == {"Python", "SQL", "Excel", "Power BI"}


def test_technical_slots_carry_saved_skill_assignment_for_batch_prompt():
    slots = build_slots(
        category_counts={"Technical Aptitude": 4},
        topics_by_category={"Technical Aptitude": ["Programming Fundamentals", "SQL Queries & Joins", "Machine Learning Fundamentals", "Power BI & Data Visualization"]},
        technical_role="Data Analyst",
        technical_skills=["Python", "Machine Learning", "SQL", "Power BI"],
        difficulty="Easy",
    )
    assert {slot["technical_skill"] for slot in slots} == {"Python", "Machine Learning", "SQL", "Power BI"}
    assert [slot["technical_skill"] for slot in slots] == [
        "Python", "SQL", "Machine Learning", "Power BI",
    ]


def test_category_practice_reconciles_stale_broad_topics_to_saved_skills():
    slots = build_category_slots(
        "Technical Aptitude", "Beginner",
        topics=["Variables & Data Types"] * 10,
        technical_role="Data Analyst",
        technical_skills=["Python", "Machine Learning", "SQL", "Power BI"],
    )
    assert {slot["topic"] for slot in slots} == {
        "Programming Fundamentals", "Machine Learning Fundamentals",
        "SQL Queries & Joins", "Power BI & Data Visualization",
    }


def test_mixed_topic_schedule_skips_categories_configured_as_zero(monkeypatch):
    """Disabled Mixed categories must not reach the positive-count selector."""
    calls = []
    monkeypatch.setattr(
        "backend.app.services.topic_selection_service._shared_history_row",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "backend.app.services.topic_selection_service.select_topics_for_attempt",
        lambda *args, **kwargs: calls.append((args, kwargs)) or ["Logical topic"],
    )

    schedules = select_mixed_topics_for_attempt(
        "learner-1",
        {"Technical Aptitude": 0, "Logical Reasoning": 1},
    )

    assert schedules["Technical Aptitude"] == []
    assert schedules["Logical Reasoning"] == ["Logical topic"]
    assert len(calls) == 1


def test_mixed_technical_schedule_rotates_role_topics_between_attempts(monkeypatch):
    class History:
        topics_used = [
            "Programming Fundamentals",
            "Machine Learning Fundamentals",
            "SQL Queries & Joins",
            "Power BI & Data Visualization",
        ]

    monkeypatch.setattr(
        "backend.app.services.topic_selection_service._shared_history_row",
        lambda *args, **kwargs: History(),
    )
    schedule = select_mixed_topics_for_attempt(
        "learner-1",
        {"Technical Aptitude": 5},
        technical_role="Data Analyst",
        technical_skills=["Python", "Machine Learning", "SQL", "Power BI"],
        technical_level="Beginner",
    )["Technical Aptitude"]

    assert len(schedule) == 5
    assert set(schedule) != set(History.topics_used)
    assert any(topic not in History.topics_used for topic in schedule)


def test_mixed_technical_schedule_repeats_only_saved_skill_topics_for_extra_slots(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.topic_selection_service._shared_history_row",
        lambda *args, **kwargs: None,
    )
    schedule = select_mixed_topics_for_attempt(
        "learner-1",
        {"Technical Aptitude": 8},
        technical_role="Data Analyst",
        technical_skills=["Python", "Machine Learning", "SQL", "Power BI"],
        technical_level="Beginner",
    )["Technical Aptitude"]
    skill_topics = set(role_skill_topics_for_level(
        "Data Analyst", ["Python", "Machine Learning", "SQL", "Power BI"], "Beginner"
    ))
    assert len(schedule) == 8
    assert set(schedule) <= skill_topics
