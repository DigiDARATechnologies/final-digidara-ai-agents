"""Fast, stateful topic rotation for live Category Practice generation."""

import random
import uuid

from flask import current_app

from ..extensions import db
from ..models.topic_history import LearnerLastTopics
from ..topic_config import (
    select_rotating_topic_names,select_weighted_topic_names,
    topic_definitions_for,topic_is_starred,
)
from ..models.base import utcnow


SHARED_HISTORY_SCOPE="Shared"


def _shared_history_row(learner_id,category,lock=False):
    query=LearnerLastTopics.query.filter_by(
        learner_id=learner_id,category_id=category,level=SHARED_HISTORY_SCOPE,
    )
    if lock:
        query=query.with_for_update()
    return query.first()


def _recent_history_row(learner_id,category):
    """Return shared history, falling back to pre-shared legacy rows."""
    shared=_shared_history_row(learner_id,category)
    if shared:
        return shared
    return LearnerLastTopics.query.filter_by(
        learner_id=learner_id,category_id=category,
    ).order_by(LearnerLastTopics.updated_at.desc()).first()


def choose_topics(pool, previous_topics, count, rng=None):
    """Choose a varied schedule, avoiding the immediately previous set first."""
    if count < 1:
        raise ValueError("Category Practice requires at least one topic")
    eligible = list(dict.fromkeys(str(topic).strip() for topic in pool if str(topic).strip()))
    if not eligible:
        raise ValueError("Category Practice topic pool is empty")

    rng = rng or random.SystemRandom()
    if len(eligible)<count:
        current_app.logger.warning(
            "Topic selection content gap eligible_topics=%s requested=%s; allowing repeated topics",
            len(eligible), count,
        )
    definitions=[{"name":topic,"is_starred":False} for topic in eligible]
    return select_rotating_topic_names(definitions,previous_topics,count,rng)


def select_topics_for_attempt(
    learner_id,category,level,count,*,apply_priority_weighting=True,
):
    """Select using the latest successful attempt in this category.

    A one-attempt category-wide window provides useful non-starred variety
    without exhausting smaller pools. The persisted rows remain level-scoped
    so an active attempt can recover its exact stable schedule.
    """
    row=_recent_history_row(learner_id,category)
    previous = row.topics_used if row and isinstance(row.topics_used, list) else []
    definitions=topic_definitions_for(category)
    selector=(select_weighted_topic_names if apply_priority_weighting else select_rotating_topic_names)
    selected=selector(definitions,previous,count,random.SystemRandom())
    starred=sum(topic_is_starred(category,topic) for topic in selected)
    current_app.logger.info(
        "Topics selected learner=%s category=%s level=%s priority_weighting=%s rotation_window_attempts=1 previous=%s selected=%s starred=%s non_starred=%s",
        learner_id,category,level,apply_priority_weighting,previous,selected,starred,len(selected)-starred,
    )
    return selected


def save_last_topics(learner_id, category, level, topics):
    """Overwrite shared category history after test generation succeeds."""
    row=_shared_history_row(learner_id,category,lock=True)
    if not row:
        row = LearnerLastTopics(
            id=str(uuid.uuid4()), learner_id=learner_id,
            category_id=category, level=SHARED_HISTORY_SCOPE,
        )
        db.session.add(row)
    row.topics_used = list(topics)
    row.updated_at = utcnow()
    return row


def attempt_topic_schedule(test, count):
    """Return the stable topic schedule for an active practice attempt."""
    transient = getattr(test, "_category_topic_schedule", None)
    if isinstance(transient, list) and len(transient) >= count:
        return list(transient[:count])

    row=_shared_history_row(test.student_id,test.selected_category)
    if not row:
        # Compatibility for attempts created before shared history was added.
        row=LearnerLastTopics.query.filter_by(
            learner_id=test.student_id,category_id=test.selected_category,
            level=test.selected_level,
        ).first()
    if row and isinstance(row.topics_used, list) and len(row.topics_used) >= count:
        return list(row.topics_used[:count])

    # Compatibility for an active test created before this migration. A seed
    # derived from the immutable test id makes the fallback stable per request.
    seeded = random.Random(f"{test.id}:{test.selected_category}:{test.selected_level}")
    return select_weighted_topic_names(
        topic_definitions_for(test.selected_category),[],count,seeded,
    )


def select_mixed_topics_for_attempt(learner_id,category_counts):
    """Create equal-probability, all-topic-rotating Mixed schedules."""
    return {
        category:select_topics_for_attempt(
            learner_id,category,"Mixed",int(count),apply_priority_weighting=False,
        )
        for category,count in category_counts.items()
    }


def save_mixed_topics(learner_id,topics_by_category):
    """Persist every successful Mixed category schedule to shared history."""
    for category,topics in topics_by_category.items():
        save_last_topics(learner_id,category,"Mixed",topics)


def mixed_attempt_topic_schedules(test):
    """Reload the immutable per-category schedule for an active Mixed test."""
    transient=getattr(test,"_mixed_topic_schedules",None)
    counts=test.mixed_category_counts or {}
    if isinstance(transient,dict) and all(
        len(transient.get(category,()))>=int(count)
        for category,count in counts.items()
    ):
        return {category:list(transient[category][:int(count)]) for category,count in counts.items()}

    schedules={}
    for category,count in counts.items():
        row=_shared_history_row(test.student_id,category)
        if row and isinstance(row.topics_used,list) and len(row.topics_used)>=int(count):
            schedules[category]=list(row.topics_used[:int(count)])
        else:
            seeded=random.Random(f"{test.id}:{category}:mixed-history-fallback")
            schedules[category]=select_rotating_topic_names(
                topic_definitions_for(category),[],int(count),seeded,
            )
    return schedules


def replace_attempt_topic(test, sequence, failed_topic):
    """Replace one rejected topic without changing the rest of the test plan."""
    count = int(test.total_questions)
    schedule = attempt_topic_schedule(test, count)
    used = {topic.casefold() for topic in schedule}
    definitions=topic_definitions_for(test.selected_category)
    failed_is_starred=topic_is_starred(test.selected_category,failed_topic)
    candidates = [
        item["name"] for item in definitions
        if item["is_starred"]==failed_is_starred
        and item["name"].casefold() not in used
        and item["name"].casefold()!=failed_topic.casefold()
    ]
    if not candidates:
        candidates = [
            item["name"] for item in definitions
            if item["name"].casefold() not in used
            and item["name"].casefold()!=failed_topic.casefold()
        ]
    if not candidates:
        return failed_topic
    replacement = random.SystemRandom().choice(candidates)
    schedule[sequence - 1] = replacement
    test._category_topic_schedule = schedule

    row=_shared_history_row(test.student_id,test.selected_category)
    if not row:
        row=LearnerLastTopics.query.filter_by(
            learner_id=test.student_id,category_id=test.selected_category,
            level=test.selected_level,
        ).first()
    if row:
        row.topics_used = list(schedule)
        row.updated_at = utcnow()
    current_app.logger.warning(
        "Category Practice topic replaced test=%s sequence=%s failed_topic=%s replacement=%s",
        test.id, sequence, failed_topic, replacement,
    )
    return replacement
