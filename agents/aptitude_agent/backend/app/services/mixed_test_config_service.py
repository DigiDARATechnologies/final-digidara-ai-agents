"""Per-learner Mixed Test category-count configuration."""

import uuid

from ..extensions import db
from ..models import LearnerMixedTestConfig
from ..models.base import utcnow
from .test_generation import CATEGORIES, DISTRIBUTION


# A category may be omitted from a Mixed Test by setting its count to zero.
# The update validator still requires at least one question across all
# categories so an empty assessment cannot be started.
MIN_CATEGORY_QUESTIONS = 0
MAX_CATEGORY_QUESTIONS = 10
MAX_MIXED_TEST_QUESTIONS = 60

MIXED_CATEGORY_IDS = {
    "Quantitative Aptitude": "quantitative_aptitude",
    "Logical Reasoning": "logical_reasoning",
    "Verbal Ability": "verbal_ability",
    "Analytical Reasoning": "analytical_reasoning",
    "Computer Fundamentals": "computer_fundamentals",
    "Technical Aptitude": "technical_aptitude",
}

MIXED_CATEGORY_DEFINITIONS = tuple(
    {
        "category_id": MIXED_CATEGORY_IDS[name],
        "category_name": name,
        "default_count": default_count,
    }
    for name, default_count in zip(CATEGORIES, DISTRIBUTION)
)


def ensure_mixed_test_config(learner_id):
    """Return all six rows, seeding any missing defaults in one transaction."""
    existing = {
        row.category_id: row
        for row in LearnerMixedTestConfig.query.filter_by(learner_id=learner_id).all()
    }
    rows = []
    for definition in MIXED_CATEGORY_DEFINITIONS:
        row = existing.get(definition["category_id"])
        if not row:
            row = LearnerMixedTestConfig(
                id=str(uuid.uuid4()), learner_id=learner_id,
                category_id=definition["category_id"],
                category_name=definition["category_name"],
                question_count=definition["default_count"],
            )
            db.session.add(row)
        elif row.category_name != definition["category_name"]:
            row.category_name = definition["category_name"]
        # Repair legacy values defensively as configurations are loaded. The
        # migration performs the same correction for existing environments.
        if row.question_count < MIN_CATEGORY_QUESTIONS:
            row.question_count = MIN_CATEGORY_QUESTIONS
        elif row.question_count > MAX_CATEGORY_QUESTIONS:
            row.question_count = MAX_CATEGORY_QUESTIONS
        rows.append(row)
    db.session.flush()
    return rows


def mixed_counts_by_name(learner_id):
    return {
        row.category_name: row.question_count
        for row in ensure_mixed_test_config(learner_id)
    }


def serialize_mixed_test_config(rows):
    by_id = {row.category_id: row for row in rows}
    categories = [
        {
            "category_id": definition["category_id"],
            "category_name": definition["category_name"],
            "question_count": by_id[definition["category_id"]].question_count,
            "default_count": definition["default_count"],
        }
        for definition in MIXED_CATEGORY_DEFINITIONS
    ]
    return {
        "categories": categories,
        "total_questions": sum(item["question_count"] for item in categories),
        "limits": {
            "min_per_category": MIN_CATEGORY_QUESTIONS,
            "max_per_category": MAX_CATEGORY_QUESTIONS,
            "max_total": MAX_MIXED_TEST_QUESTIONS,
        },
    }


def validate_mixed_test_update(body):
    if not isinstance(body, dict) or not isinstance(body.get("categories"), list):
        raise ValueError("Provide all six category counts")
    submitted = body["categories"]
    expected_ids = {item["category_id"] for item in MIXED_CATEGORY_DEFINITIONS}
    if len(submitted) != len(expected_ids):
        raise ValueError("Provide exactly one count for each of the six categories")
    counts = {}
    for item in submitted:
        if not isinstance(item, dict):
            raise ValueError("Each category configuration must be an object")
        category_id = str(item.get("category_id") or "").strip()
        count = item.get("question_count")
        if category_id not in expected_ids or category_id in counts:
            raise ValueError("Category configuration contains an invalid or duplicate category")
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("Every question count must be a whole number from 0 to 10")
        if count < MIN_CATEGORY_QUESTIONS or count > MAX_CATEGORY_QUESTIONS:
            raise ValueError("Every question count must be between 0 and 10")
        counts[category_id] = count
    if set(counts) != expected_ids:
        raise ValueError("Provide exactly one count for each of the six categories")
    total = sum(counts.values())
    if total == 0:
        raise ValueError("Select at least one question across the categories")
    if total > MAX_MIXED_TEST_QUESTIONS:
        raise ValueError("A Mixed Test cannot exceed 60 questions")
    return counts


def update_mixed_test_config(learner_id, counts):
    rows = ensure_mixed_test_config(learner_id)
    for row in rows:
        row.question_count = counts[row.category_id]
        row.updated_at = utcnow()
    db.session.flush()
    return rows
