import random

from flask import Flask

from backend.app.services.test_generation import CATEGORY_PRACTICE_QUESTION_COUNT, CATEGORIES, DISTRIBUTION, build_category_slots, build_slots
from backend.app.services.topic_selection_service import choose_topics
from backend.app.topic_config import (
    CATEGORY_PRACTICE_TOPICS,CATEGORY_TOPIC_CONFIG,PRACTICE_LEVELS,
    select_rotating_topic_names,select_weighted_topic_names,
    topic_definitions_for,topic_is_starred,topics_for,
)


def test_every_category_and_level_has_a_large_unique_topic_pool():
    assert set(CATEGORY_PRACTICE_TOPICS)==set(CATEGORIES)
    for category in CATEGORIES:
        assert set(CATEGORY_PRACTICE_TOPICS[category])==set(PRACTICE_LEVELS)
        for level in PRACTICE_LEVELS:
            pool=topics_for(category,level)
            assert len(pool)>=10
            assert len({topic.casefold() for topic in pool})==len(pool)
            assert all(set(item)=={"name","is_starred"} for item in CATEGORY_TOPIC_CONFIG[category][level])


def test_research_topics_are_only_assigned_to_the_confirmed_category():
    for category in CATEGORY_TOPIC_CONFIG:
        names={item["name"].casefold() for item in topic_definitions_for(category)}
        restricted={name for name in names if "data sufficiency" in name or "cause & effect" in name}
        if category=="Logical Reasoning":
            assert "data sufficiency" in restricted
            assert "cause & effect logic" in restricted
        else:
            assert not restricted


def test_analytical_reasoning_has_only_the_approved_starred_topics():
    starred={
        item["name"] for item in topic_definitions_for("Analytical Reasoning")
        if item["is_starred"]
    }
    assert starred=={
        "Pattern Recognition","Logical Puzzles","Critical Thinking","Matrix Reasoning",
    }


def test_analytical_nonstarred_topics_rotate_behind_fresh_topics():
    definitions=topic_definitions_for("Analytical Reasoning")
    previous=[item["name"] for item in definitions if not item["is_starred"]][:10]
    selected=select_weighted_topic_names(definitions,previous,10,random.Random(27))
    selected_nonstarred={
        topic for topic in selected
        if not topic_is_starred("Analytical Reasoning",topic)
    }
    assert selected_nonstarred
    assert selected_nonstarred.isdisjoint(previous)


def test_only_nonstarred_topics_rotate_and_exhausted_pool_resets():
    category="Computer Fundamentals"
    definitions=topic_definitions_for(category)
    first=select_weighted_topic_names(definitions,[],10,random.Random(91))
    second=select_weighted_topic_names(definitions,first,10,random.Random(91))
    first_starred={topic for topic in first if topic_is_starred(category,topic)}
    second_starred={topic for topic in second if topic_is_starred(category,topic)}
    first_nonstarred={topic for topic in first if not topic_is_starred(category,topic)}
    second_nonstarred={topic for topic in second if not topic_is_starred(category,topic)}
    # Starred topics are eligible again immediately; unlike non-starred
    # topics, overlap is expected and is not excluded by history.
    assert first_starred&second_starred
    assert first_nonstarred.isdisjoint(second_nonstarred)

    all_nonstarred=[item["name"] for item in definitions if not item["is_starred"]]
    reset=select_weighted_topic_names(definitions,all_nonstarred,10,random.Random(92))
    assert len(reset)==10
    assert len(reset)==len(set(reset))
    assert any(not topic_is_starred(category,topic) for topic in reset)


def test_topic_selection_avoids_the_immediately_previous_attempt():
    pool=topics_for("Quantitative Aptitude","Beginner")
    previous=list(pool[:CATEGORY_PRACTICE_QUESTION_COUNT])
    selected=choose_topics(
        pool,previous,CATEGORY_PRACTICE_QUESTION_COUNT,random.Random(42),
    )
    assert len(selected)==CATEGORY_PRACTICE_QUESTION_COUNT
    assert len(set(selected))==CATEGORY_PRACTICE_QUESTION_COUNT
    assert set(pool)-set(previous) <= set(selected)
    fresh_count=len(set(pool)-set(previous))
    assert len(set(selected)&set(previous))==CATEGORY_PRACTICE_QUESTION_COUNT-fresh_count
    assert selected!=previous


def test_first_attempt_selects_distinct_topics_and_builds_matching_slots():
    pool=topics_for("Technical Aptitude","Advanced")
    selected=choose_topics(
        pool,[],CATEGORY_PRACTICE_QUESTION_COUNT,random.Random(7),
    )
    slots=build_category_slots("Technical Aptitude","Advanced",selected)
    assert [slot["topic"] for slot in slots]==selected
    assert all(slot["difficulty"]=="Hard" for slot in slots)


def test_small_pool_repeats_without_failing():
    app=Flask(__name__)
    with app.app_context():
        selected=choose_topics(["One","Two"],["One"],5,random.Random(3))
    assert len(selected)==5
    assert set(selected)=={"One","Two"}
    assert all(left!=right for left,right in zip(selected,selected[1:]))


def test_direct_category_slot_calls_do_not_use_the_legacy_fixed_order():
    first=build_category_slots("Computer Fundamentals","Beginner",seed="attempt-one")
    second=build_category_slots("Computer Fundamentals","Beginner",seed="attempt-two")
    first_topics=[slot["topic"] for slot in first]
    second_topics=[slot["topic"] for slot in second]
    assert first_topics!=second_topics
    assert len(set(first_topics))==CATEGORY_PRACTICE_QUESTION_COUNT
    assert len(set(second_topics))==CATEGORY_PRACTICE_QUESTION_COUNT
    assert set(first_topics)<=set(CATEGORIES["Computer Fundamentals"])
    assert set(second_topics)<=set(CATEGORIES["Computer Fundamentals"])


def test_mixed_slots_vary_by_attempt_but_keep_distribution_and_difficulty_plan():
    first=build_slots(seed="attempt-one")
    second=build_slots(seed="attempt-two")
    assert first!=second
    assert [slot["difficulty"] for slot in first]==[slot["difficulty"] for slot in second]
    for category,count in zip(CATEGORIES,DISTRIBUTION):
        assert sum(slot["category"]==category for slot in first)==count
        assert sum(slot["category"]==category for slot in second)==count


def test_mixed_slot_seed_is_stable_within_one_live_attempt():
    assert build_slots(seed="same-test-id")==build_slots(seed="same-test-id")


def test_mixed_slots_preserve_history_selected_category_schedules():
    counts={category:3 for category in CATEGORIES}
    selected={
        category:select_rotating_topic_names(
            topic_definitions_for(category),[],count,random.Random(f"history:{category}"),
        )
        for category,count in counts.items()
    }
    schedule=build_slots(
        seed="history-aware-mixed",category_counts=counts,
        topics_by_category=selected,
    )
    for category,topics in selected.items():
        assert {slot["topic"] for slot in schedule if slot["category"]==category}==set(topics)


def test_five_mixed_attempts_rotate_all_topics():
    counts={category:3 for category in CATEGORIES}
    previous={category:[] for category in CATEGORIES}
    for attempt in range(5):
        selected={
            category:select_rotating_topic_names(
                topic_definitions_for(category),previous[category],count,
                random.Random(f"mixed-rotation:{attempt}:{category}"),
            )
            for category,count in counts.items()
        }
        schedule=build_slots(
            seed=f"mixed-rotation:{attempt}",category_counts=counts,
            topics_by_category=selected,
        )
        for category in CATEGORIES:
            topics=[slot["topic"] for slot in schedule if slot["category"]==category]
            assert len(topics)==len(set(topics))
            assert set(previous[category]).isdisjoint(topics)
            previous[category]=topics


def test_mixed_equal_selector_ignores_priority_metadata():
    definitions=[
        {"name":f"Priority {index}","is_starred":True} for index in range(2)
    ]+[
        {"name":f"Regular {index}","is_starred":False} for index in range(8)
    ]
    selected=[]
    for attempt in range(2000):
        selected.extend(select_rotating_topic_names(
            definitions,[],1,random.Random(f"equal-mixed:{attempt}"),
        ))
    priority=sum(topic.startswith("Priority") for topic in selected)
    # Equal topic probability follows the pool's natural 2/10 composition,
    # rather than forcing the former 50% priority bucket.
    assert .17<=priority/len(selected)<=.23


def test_weighted_selector_trends_to_equal_priority_buckets():
    for category in CATEGORIES:
        definitions=topic_definitions_for(category)
        selected=[]
        # Three draws stay below the smallest approved priority bucket, so
        # this measures the selector's bucket probability without exhaustion.
        for attempt in range(500):
            selected.extend(select_weighted_topic_names(definitions,[],3,random.Random(attempt)))
        starred=sum(topic_is_starred(category,topic) for topic in selected)
        ratio=starred/len(selected)
        assert .45<=ratio<=.55


def test_mixed_and_category_sessions_have_no_duplicate_topics_and_balance_over_time():
    mixed_frequency={category:{} for category in CATEGORIES}
    for attempt in range(500):
        schedule=build_slots(seed=f"mixed-{attempt}")
        for category in CATEGORIES:
            topics=[slot["topic"] for slot in schedule if slot["category"]==category]
            assert len(topics)==len(set(topics))
            for topic in topics:
                mixed_frequency[category][topic]=mixed_frequency[category].get(topic,0)+1

    for category,frequency in mixed_frequency.items():
        assert set(frequency)==set(CATEGORIES[category])
        total=sum(frequency.values())
        expected=total/len(frequency)
        # Each category has roughly 37-52 eligible labels and each schedule
        # draws only 3-5 without replacement. This broad bound catches a
        # systematic exclusion while avoiding flaky tail-frequency failures;
        # the controlled 2/10 metadata test above verifies equal probability.
        assert all(expected*.5<=count<=expected*1.5 for count in frequency.values())

    practice_totals={category:[0,0] for category in CATEGORIES}
    for category in CATEGORIES:
        for level in PRACTICE_LEVELS:
            for attempt in range(20):
                schedule=build_category_slots(category,level,seed=f"{category}-{level}-{attempt}")
                topics=[slot["topic"] for slot in schedule]
                assert len(topics)==len(set(topics))
                practice_totals[category][0]+=sum(topic_is_starred(category,topic) for topic in topics)
                practice_totals[category][1]+=len(topics)

    for category,(starred,total) in practice_totals.items():
        ratio=starred/total
        if category=="Analytical Reasoning":
            # Four approved starred labels in a ten-question unique-topic
            # session cap the attainable share at 40%.
            assert .30<=ratio<=.40
        else:
            assert .35<=ratio<=.65
