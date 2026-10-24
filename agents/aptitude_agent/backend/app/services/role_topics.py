"""Role-aware Technical Aptitude topic selection.

The public aptitude taxonomy remains unchanged.  This module only chooses a
role-relevant subset of those existing topics and supplies context to the
generation prompt.
"""
import re

from ..topic_config import topic_definitions_for


# Generic and missing roles use a language-neutral pool of existing taxonomy
# labels, preserving normal rotation and difficulty handling.
GENERIC_TECHNICAL_TOPICS = (
    "Programming Fundamentals", "Variables & Data Types", "Operators & Expressions",
    "Conditional Statements", "Loops", "Functions", "Object-Oriented Basics",
    "Object-Oriented Programming", "Data Structures and Algorithms", "Data Structures",
    "Searching Algorithms", "Sorting Algorithms", "Time Complexity", "Database Programming",
    "SQL Queries & Joins", "Database Normalization", "Debugging Basics", "API Design",
    "System Design Fundamentals", "Concurrency", "Memory Management in Programs",
)
GENERIC_TECHNICAL_TERMS = (
    "variables", "data types", "operators", "conditions", "loops", "functions",
    "classes", "objects", "inheritance", "encapsulation", "polymorphism", "abstraction",
    "arrays", "strings", "stacks", "queues", "searching", "sorting", "complexity",
    "tables", "primary keys", "foreign keys", "relationships", "joins", "sql",
    "ip addresses", "dns", "http", "https", "tcp/ip", "client-server",
    "processes", "threads", "memory management", "cpu scheduling", "sdlc", "debugging",
    "version control", "testing", "html", "css", "javascript", "apis", "problem solving",
)

SKILL_TOPIC_RULES = {
    "python": ("python", "django", "flask", "fastapi", "pandas", "numpy", "programming fundamentals", "functions", "data structures"),
    "java": ("java", "spring", "hibernate", "kotlin", "object-oriented programming", "exception handling"),
    "sql": ("sql", "mysql", "postgres", "oracle", "database", "database programming", "sql queries", "database normalization"),
    "javascript": ("javascript", "typescript", "react", "node", "frontend", "web", "html", "css", "api design"),
    "cloud": ("cloud", "aws", "azure", "gcp", "system design fundamentals", "api design", "concurrency"),
    "devops": ("devops", "docker", "kubernetes", "ci/cd", "infrastructure", "debugging basics", "system design fundamentals"),
    "testing": ("testing", "qa", "unit testing", "debugging", "debugging basics", "software testing"),
    "git": ("git", "github", "version control", "debugging basics"),
    "c": (" c ", "c++", "embedded", "programming fundamentals", "data structures", "memory management in programs"),
    "flask": ("flask", "flask web development", "api design", "database programming"),
    "excel": ("excel", "excel data analysis", "spreadsheets", "data analysis"),
    "react": ("react", "react fundamentals", "javascript", "api design", "web"),
    "machine learning": ("machine learning", "ml", "machine learning fundamentals", "data structures and algorithms", "data structures", "time complexity"),
      "power bi": ("power bi", "power bi & data visualization", "business intelligence", "database programming", "data structures", "sql queries"),
}

_SKILL_ALIAS_KEYS = {
    "py": "python",
    "python": "python",
    "ml": "machine learning",
    "machinelearning": "machine learning",
    "powerbi": "power bi",
    "businessintelligence": "power bi",
}


def normalize_technical_skills(skills):
    """Canonicalize saved-skill aliases before topic planning and validation."""
    normalized = []
    seen = set()
    for raw in skills or ():
        value = re.sub(r"\s+", " ", str(raw or "").strip())
        if not value:
            continue
        key = re.sub(r"[^a-z0-9]+", "", value.casefold())
        canonical_key = _SKILL_ALIAS_KEYS.get(key, value.casefold())
        canonical = {
            "python": "Python",
            "machine learning": "Machine Learning",
            "power bi": "Power BI",
            "sql": "SQL",
            "excel": "Excel",
        }.get(canonical_key, value)
        dedupe_key = canonical.casefold()
        if dedupe_key not in seen:
            normalized.append(canonical)
            seen.add(dedupe_key)
    return normalized


def skill_for_topic(topic, skills, fallback_index=0):
    """Pair a planned topic with the saved skill it most clearly represents."""
    values = normalize_technical_skills(skills)
    if not values:
        return None
    topic_text = str(topic or "").casefold()
    # Prefer an exact saved-skill match before broader aliases.  Python's
    # role aliases include Flask, for example, so checking aliases first can
    # incorrectly assign a Flask topic back to Python.
    for skill in values:
        skill_text = skill.casefold()
        compact_skill = re.sub(r"[^a-z0-9]+", "", skill_text)
        compact_topic = re.sub(r"[^a-z0-9]+", "", topic_text)
        if skill_text in topic_text or (compact_skill and compact_skill in compact_topic):
            return skill
    for skill in values:
        skill_text = skill.casefold()
        aliases = SKILL_TOPIC_RULES.get(skill_text, (skill_text,))
        if any(alias.casefold() in topic_text for alias in aliases):
            return skill
    return values[fallback_index % len(values)]

ROLE_TOPIC_RULES = {
    "python": {"language": "Python", "terms": ("python", "django", "flask", "fastapi", "pandas", "numpy"),
                "topics": ("Programming Fundamentals", "Variables & Data Types", "Loops", "Functions", "Data Structures", "Object-Oriented Basics", "Object-Oriented Programming", "Exception Handling", "Database Programming", "API Design")},
    "java": {"language": "Java", "terms": ("java", "spring", "hibernate", "j2ee", "kotlin"),
              "topics": ("Programming Fundamentals", "Variables & Data Types", "Functions", "Data Structures", "Object-Oriented Basics", "Object-Oriented Programming", "Exception Handling", "Database Programming", "API Design", "Constructors/Destructors/Garbage Collection")},
    # JavaScript is not one of the legacy code-format enum values. Python is
    # used only as the internal formatter fallback; the prompt still receives
    # the MERN role terms and asks for JavaScript/React/Node/MongoDB content.
    "mern": {"language": "Python", "terms": ("mern", "javascript", "react", "node", "mongodb", "frontend", "full stack", "fullstack"),
              "topics": ("Programming Fundamentals", "Variables & Data Types", "Conditional Statements", "Loops", "Functions", "Arrays", "Strings", "Object-Oriented Basics", "Object-Oriented Programming", "Data Structures", "API Design", "Database Programming", "System Design Fundamentals")},
    "dotnet": {"language": "C", "terms": (".net", "dotnet", "c#", "asp.net", "aspnet", "azure"),
                "topics": ("Programming Fundamentals", "Variables & Data Types", "Functions", "Object-Oriented Basics", "Object-Oriented Programming", "Exception Handling", "Data Structures", "Database Programming", "API Design", "System Design Fundamentals")},
    "data": {"language": "SQL", "terms": ("data analyst", "data analytics", "data scientist", "analytics", "business intelligence", "bi"),
             "topics": ("SQL Queries & Joins", "Database Programming", "Database Normalization", "Data Structures", "Time Complexity", "Searching Algorithms", "API Design", "Data Structures and Algorithms")},
    "devops": {"language": "Python", "terms": ("devops", "site reliability", "sre", "platform", "cloud", "infrastructure", "ci/cd", "docker", "kubernetes"),
                "topics": ("Programming Fundamentals", "Debugging Basics", "Data Structures", "Time Complexity", "System Design Fundamentals", "API Design", "Database Programming", "Advanced Complexity Analysis", "Concurrency")},
    "ai": {"language": "Python", "terms": ("ai", "machine learning", "ml", "deep learning", "data scientist", "nlp", "llm"),
            "topics": ("Programming Fundamentals", "Data Structures", "Data Structures and Algorithms", "Object-Oriented Basics", "Object-Oriented Programming", "Database Programming", "API Design", "Advanced Data Structures")},
}


def _role_key(role, skills=()):
    text = " ".join([str(role or ""), *(str(skill or "") for skill in skills)]).casefold()
    if any(term in text for term in ROLE_TOPIC_RULES["mern"]["terms"]):
        return "mern"
    if any(term in text for term in ROLE_TOPIC_RULES["dotnet"]["terms"]):
        return "dotnet"
    if any(term in text for term in ROLE_TOPIC_RULES["devops"]["terms"]):
        return "devops"
    if any(term in text for term in ROLE_TOPIC_RULES["data"]["terms"]):
        return "data"
    if any(term in text for term in ROLE_TOPIC_RULES["ai"]["terms"]):
        return "ai"
    if any(term in text for term in ROLE_TOPIC_RULES["java"]["terms"]):
        return "java"
    if "python" in text:
        return "python"
    return "generic"


def _skill_context(skills):
    normalized = normalize_technical_skills(skills)
    skill_terms = []
    topic_names = []
    # Include every taxonomy label that clearly names a saved skill.  The
    # previous implementation only added aliases that happened to be in the
    # generic topic list, so skills such as Machine Learning and Power BI were
    # present in the prompt but absent from the actual topic pool.
    taxonomy = tuple(item["name"] for item in topic_definitions_for("Technical Aptitude"))
    for skill in normalized:
        text = f" {skill.casefold()} "
        for key, values in SKILL_TOPIC_RULES.items():
            if any(value in text for value in values):
                if skill.casefold() not in skill_terms:
                    skill_terms.append(skill.casefold())
                for topic in taxonomy:
                    topic_text = topic.casefold()
                    if any(value.casefold() in topic_text for value in values if len(value.strip()) >= 3):
                        topic_names.append(topic)
                break
    return normalized, tuple(dict.fromkeys(skill_terms)), tuple(dict.fromkeys(topic_names))


def role_technical_context(role=None, skills=()):
    key = _role_key(role, skills)
    rule = ROLE_TOPIC_RULES.get(key)
    if rule is None:
        normalized, skill_terms, skill_topics = _skill_context(skills)
        return {"role": str(role or "").strip(), "family": "generic", "language": None,
                "terms": tuple(dict.fromkeys((*GENERIC_TECHNICAL_TERMS, *(skill.casefold() for skill in normalized)))),
                "topics": tuple(dict.fromkeys((*skill_topics, *GENERIC_TECHNICAL_TOPICS)))}
    normalized, skill_terms, skill_topics = _skill_context(skills)
    return {"role": str(role or "").strip(), "family": key, **rule,
            "terms": tuple(dict.fromkeys((*rule["terms"], *(skill.casefold() for skill in normalized)))),
            "topics": tuple(dict.fromkeys((*skill_topics, *rule["topics"]))) }


def role_topics_for_level(role, skills, level):
    """Return only configured taxonomy topics relevant to the role.

    If a role rule does not map a name at a particular level, the configured
    taxonomy is used as a safe generic fallback rather than inventing labels.
    """
    context = role_technical_context(role, skills)
    configured = topic_definitions_for("Technical Aptitude", level)
    if not context["topics"]:
        return tuple(item["name"] for item in configured)
    wanted = {name.casefold() for name in context["topics"]}
    selected_all = [item["name"] for item in configured if item["name"].casefold() in wanted]
    # Put one clearly skill-specific topic per saved skill at the front.  The
    # selector can then rotate/repeat these when the assessment has more slots
    # than skills, instead of spending most slots on generic role topics.
    skill_first = list(role_skill_topics_for_level(role, skills, level)) if skills else []
    # When saved skills are available, keep the pool skill-specific.  Broad
    # role topics were the source of provider drift (for example SQL output
    # assigned to a generic Data Structures slot), which correctly exhausted
    # validation retries and surfaced as a 503.
    selected = tuple(dict.fromkeys(skill_first)) or tuple(dict.fromkeys(selected_all))
    return selected or tuple(item["name"] for item in configured)


def role_topics_for_category(role, skills):
    context = role_technical_context(role, skills)
    if not context["topics"]:
        return tuple(item["name"] for item in topic_definitions_for("Technical Aptitude"))
    wanted = {name.casefold() for name in context["topics"]}
    return tuple(item["name"] for item in topic_definitions_for("Technical Aptitude")
                 if item["name"].casefold() in wanted)


def role_skill_topics_for_level(role, skills, level):
    """Return one distinct taxonomy topic for each saved technical skill.

    Mixed tests can contain only a few Technical Aptitude questions.  Giving
    each available skill its own topic keeps a five-question technical slice
    broad instead of repeatedly asking about the first role topic.  The
    returned labels always come from the existing taxonomy.
    """
    normalized_skills = normalize_technical_skills(skills)
    configured = [item["name"] for item in topic_definitions_for("Technical Aptitude", level)]
    # Keep this helper independent from role_topics_for_level: that function
    # uses this helper to prioritize the saved skills, so calling it here
    # would recurse while building the pool.
    role_pool = configured
    if not normalized_skills:
        return tuple()
    selected = []
    used = set()
    for skill in normalized_skills:
        text = skill.casefold()
        compact_text = re.sub(r"[^a-z0-9]+", "", text)
        candidates = []
        # Prefer a topic named after the skill itself (Machine Learning and
        # Power BI in particular also have broad data-structure aliases).
        exact = [topic for topic in configured if text in topic.casefold() or compact_text in re.sub(r"[^a-z0-9]+", "", topic.casefold())]
        candidates.extend(exact)
        for key, values in SKILL_TOPIC_RULES.items():
            if any(value in text or re.sub(r"[^a-z0-9]+", "", value.casefold()) in compact_text for value in values):
                candidates.extend(topic for topic in configured if any(value in topic.casefold() for value in values))
        candidates.extend(topic for topic in role_pool if topic not in candidates)
        topic = next((item for item in candidates if item.casefold() not in used), None)
        if topic:
            selected.append(topic)
            used.add(topic.casefold())
    return tuple(selected)
