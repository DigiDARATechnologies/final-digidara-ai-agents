import logging
import os

import yaml


logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "categories.yaml")
CONFIG_PATH_ENV = "JOBS_CATEGORIES_CONFIG_PATH"

OTHER_CATEGORY = "other"
OTHER_LABEL = "Other"

# Used only if categories.yaml is missing or malformed, so classification
# never silently stops working because of a bad config file.
#
# `keywords` classifies noisy free-text job titles/descriptions, so they
# are specific multi-word phrases to avoid false positives. `course_keywords`
# classifies a certification course's short, curated name (e.g. "Python",
# "AI/ML") instead, so it can safely use broader, single words.
DEFAULT_CATEGORIES = [
    {
        "id": "gen_ai_agentic_ai",
        "label": "Gen AI & Agentic AI",
        "related_categories": ["ai_ml", "python_full_stack", "data_science"],
        "keywords": [
            "generative ai", "gen ai", "genai", "agentic ai", "agentic workflows", "agentic systems",
            "large language model", " llm ", "llm engineer", "prompt engineer",
            "langchain", "langgraph", "retrieval augmented generation", "rag pipeline", "rag system",
            "ai agent", "autonomous agent", "conversational ai",
        ],
        "course_keywords": [
            "generative ai", "gen ai", "genai", "agentic ai", "agentic",
            "large language model", "llm",
        ],
    },
    {
        "id": "ai_ml",
        "label": "AI/ML",
        "related_categories": ["gen_ai_agentic_ai", "data_science", "python_full_stack"],
        "keywords": [
            "machine learning", "deep learning", "artificial intelligence",
            "computer vision", "natural language processing", " nlp ",
            "ai engineer", "ml engineer", "mlops", "neural network",
            "pytorch", "tensorflow",
        ],
        "course_keywords": [
            "machine learning", "deep learning", "artificial intelligence",
            "ai/ml", "ai / ml", "ai-ml", "ai & ml", " ai ", " ml ",
        ],
    },
    {
        "id": "data_science",
        "label": "Data Science",
        "related_categories": ["data_analytics", "ai_ml", "python_full_stack", "gen_ai_agentic_ai"],
        "keywords": ["data scientist", "data science", "predictive modeling", "statistician"],
        "course_keywords": ["data science"],
    },
    {
        "id": "data_analytics",
        "label": "Data Analytics",
        "related_categories": ["data_science", "python_full_stack"],
        "keywords": [
            "data analyst", "business analyst", "bi analyst", "business intelligence",
            "data analytics", "tableau", "power bi", "reporting analyst", "sql analyst",
        ],
        "course_keywords": ["data analytics", "data analysis"],
    },
    {
        "id": "python_full_stack",
        "label": "Python Full Stack",
        "related_categories": ["data_analytics", "data_science", "ai_ml", "gen_ai_agentic_ai"],
        "keywords": [
            "python developer", "full stack", "fullstack", "full-stack", "django", "flask",
            "backend developer", "backend engineer", "software engineer", "web developer",
            "api developer",
        ],
        "course_keywords": ["python", "full stack", "fullstack", "full-stack"],
    },
    {
        "id": "digital_marketing",
        "label": "Digital Marketing",
        # Deliberately empty: marketing doesn't share a technical skill base
        # with the Python/data/AI cluster above, so it must never bleed
        # into those students' "broader relevant" results.
        "related_categories": [],
        "keywords": [
            "digital marketing", " seo ", " sem ", " ppc ", "social media marketing",
            "content marketing", "growth marketing", "performance marketing",
            "marketing specialist", "marketing analyst", "brand marketing", "media planner",
        ],
        "course_keywords": ["digital marketing", "marketing"],
    },
]


def _config_path():
    return os.getenv(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH)


def load_categories(path=None):
    """Load the ordered category rules, falling back to the built-in defaults.

    A missing file, invalid YAML, or a malformed `categories` list all
    degrade to DEFAULT_CATEGORIES rather than raising, so a bad edit to
    categories.yaml can't silently turn off job categorization.
    """
    path = path or _config_path()
    if not os.path.exists(path):
        return [dict(category) for category in DEFAULT_CATEGORIES]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError:
        logger.exception("[Jobs][Categories] Failed to parse categories config at %s", path)
        return [dict(category) for category in DEFAULT_CATEGORIES]

    raw_categories = data.get("categories") if isinstance(data, dict) else None
    if not isinstance(raw_categories, list) or not raw_categories:
        return [dict(category) for category in DEFAULT_CATEGORIES]

    known_ids = {str(entry.get("id") or "").strip() for entry in raw_categories if isinstance(entry, dict)}

    cleaned = []
    for entry in raw_categories:
        if not isinstance(entry, dict):
            continue
        category_id = str(entry.get("id") or "").strip()
        label = str(entry.get("label") or "").strip()
        keywords = entry.get("keywords") or []
        if not category_id or not label or not isinstance(keywords, list) or not keywords:
            continue
        keywords = [str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()]
        course_keywords_raw = entry.get("course_keywords")
        if isinstance(course_keywords_raw, list) and course_keywords_raw:
            course_keywords = [str(keyword).strip().lower() for keyword in course_keywords_raw if str(keyword).strip()]
        else:
            course_keywords = keywords
        related_raw = entry.get("related_categories")
        if isinstance(related_raw, list):
            # Silently drop unknown/self ids rather than raising, so a typo
            # in one relation doesn't take down the whole config file.
            related = [
                str(related_id).strip() for related_id in related_raw
                if str(related_id).strip() in known_ids and str(related_id).strip() != category_id
            ]
        else:
            related = []
        cleaned.append({
            "id": category_id,
            "label": label,
            "keywords": keywords,
            "course_keywords": course_keywords,
            "related_categories": related,
        })
    return cleaned or [dict(category) for category in DEFAULT_CATEGORIES]


def related_category_ids(category_id, categories=None):
    """Return the set of category ids related to `category_id` (not including itself).

    Used to broaden "show me jobs for my course" into "show me jobs for my
    course plus the roles it commonly feeds into" (e.g. a Python course
    also surfaces Data Analyst/Data Scientist/AI-ML roles) without ever
    pulling in a category with no real skill overlap (e.g. Digital
    Marketing stays isolated). Unknown category ids return an empty set.
    """
    categories = load_categories() if categories is None else categories
    for category in categories:
        if category["id"] == category_id:
            return set(category.get("related_categories") or [])
    return set()


def category_labels(categories=None):
    categories = load_categories() if categories is None else categories
    labels = {category["id"]: category["label"] for category in categories}
    labels[OTHER_CATEGORY] = OTHER_LABEL
    return labels


def categorize_text(text, categories=None):
    """Return the id of the first category whose keyword appears in `text`."""
    categories = load_categories() if categories is None else categories
    padded = f" {(text or '').lower()} "
    for category in categories:
        if any(keyword in padded for keyword in category["keywords"]):
            return category["id"]
    return OTHER_CATEGORY


def categorize_course_name(course_name, categories=None):
    """Return the id of the first category matching a certification course's name.

    Uses each category's `course_keywords` (broader/shorter than the
    `keywords` used for noisy job text) since a course name is short,
    curated text from DigiDARA's own catalog, e.g. "Python" or "AI/ML" —
    not a scraped job title where a bare "python" could just be one of
    many tools listed for an unrelated role.
    """
    categories = load_categories() if categories is None else categories
    padded = f" {(course_name or '').lower()} "
    for category in categories:
        if any(keyword in padded for keyword in category.get("course_keywords") or category["keywords"]):
            return category["id"]
    return OTHER_CATEGORY


def categorize_job(title, department="", description="", categories=None):
    """Classify a job into a course category from its title and department only.

    `description` is intentionally never used for classification, even
    though it's still accepted as a parameter for backward compatibility.
    Verified against real collected jobs: descriptions are full of company
    boilerplate that has nothing to do with the specific role - e.g. every
    job at an "agentic AI" company mentions "AI agents" in its intro
    paragraph, which previously miscategorized that company's "Process
    Specialist" and "Project Coordinator" postings as Gen AI & Agentic AI,
    and one company's generic "we value people" blurb miscategorized its
    "IT Admin" and HR postings as Digital Marketing. Title and department
    are curated by the employer specifically to describe the role, so they
    are a far more reliable signal - this trades a little recall (a
    genuinely relevant job with a generic title won't get tagged) for a
    lot of precision (no more unrelated roles leaking into a category).
    """
    categories = load_categories() if categories is None else categories
    return categorize_text(f"{title or ''} {department or ''}", categories)
