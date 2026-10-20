from backend.app.services.test_generation import LEARNER_LEVEL_DIFFICULTY, PROFESSIONAL_RIGOR, _batch_prompt, build_category_slots, build_slots


COUNTS = {"Quantitative Aptitude": 3, "Logical Reasoning": 2}


def test_a_mixed_test_at_a_level_sets_every_question_at_that_difficulty():
    slots = build_slots(seed="s", category_counts=COUNTS, difficulty=LEARNER_LEVEL_DIFFICULTY["hard"])
    assert len(slots) == 5 and {slot["difficulty"] for slot in slots} == {"Hard"}
    assert all("rigor" not in slot for slot in slots)


def test_without_a_level_the_mixed_test_keeps_its_old_mix():
    slots = build_slots(seed="s", category_counts=COUNTS)
    assert {slot["difficulty"] for slot in slots} == {"Easy"}  # the first slots of the old mix


def test_professional_is_hard_with_professional_rigor_and_the_prompt_explains_it():
    slots = build_category_slots("Logical Reasoning", "Advanced", ["Syllogism"], rigor=PROFESSIONAL_RIGOR)
    assert {slot["difficulty"] for slot in slots} == {"Hard"} and {slot["rigor"] for slot in slots} == {"professional"}
    prompt = _batch_prompt(slots[:1], [], [], "batch")
    assert '"rigor":"professional"' in prompt and 'rigor "professional": above Hard' in prompt
