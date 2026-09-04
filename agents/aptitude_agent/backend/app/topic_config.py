"""Category Practice topic taxonomy used to steer live Groq generation.

This module contains topic labels only. It is not a question bank and stores
no question text, options, answers, explanations, or hints.
"""

PRACTICE_LEVELS = ("Beginner", "Intermediate", "Advanced")


_TOPIC_NAMES_BY_LEVEL = {
    "Quantitative Aptitude": {
        "Beginner": (
            "Percentages", "Ratio & Proportion", "Average", "Profit & Loss",
            "Simple Interest", "Time & Work", "Time & Distance", "Number Systems",
            "Ages", "Fractions & Decimals", "LCM & HCF", "Basic Data Interpretation",
            "Discounts", "Number Series & Patterns", "Simplification", "Surds & Indices",
        ),
        "Intermediate": (
            "Compound Interest", "Mixtures & Alligations", "Pipes & Cisterns",
            "Boats & Streams", "Trains", "Partnership", "Algebraic Equations",
            "Geometry", "Mensuration", "Advanced Data Interpretation",
            "Permutations & Combinations", "Probability",
            "Time & Work Applications", "Time, Speed & Distance Applications",
        ),
        "Advanced": (
            "Advanced Probability", "Advanced Permutations & Combinations",
            "Complex Mixtures", "Functions & Graphs",
            "Coordinate Geometry", "Advanced Mensuration", "Sequences & Series",
            "Logarithms", "Set Theory", "Optimization", "Multi-Chart Data Interpretation",
            "Advanced Time & Work", "Advanced Time, Speed & Distance",
        ),
    },
    "Logical Reasoning": {
        "Beginner": (
            "Number Series", "Alphabet Series", "Coding-Decoding", "Direction Sense",
            "Blood Relations", "Analogy", "Classification", "Odd One Out",
            "Ranking & Ordering", "Calendar Basics", "Clock Basics", "Simple Venn Diagrams",
            "Series Completion", "Linear & Circular Grid Puzzles", "Grid Shifting & Cubes",
        ),
        "Intermediate": (
            "Syllogism", "Linear Seating Arrangement", "Circular Seating Arrangement",
            "Logical Puzzles", "Statement & Conclusion", "Statement & Assumption",
            "Data Sufficiency", "Input-Output", "Logical Sequence", "Cause & Effect Logic",
            "Course of Action", "Intermediate Venn Diagrams",
            "Matrix/Attributes Matching", "Selection/Eligibility Criteria Tables",
            "Symbolic & Coded Inequalities", "Input-Output Sequential Tracing",
            "Statement - Assumptions & Courses of Action",
        ),
        "Advanced": (
            "Complex Seating Arrangement", "Advanced Logic Puzzles", "Critical Reasoning",
            "Assertion & Reason", "Decision Making", "Advanced Data Sufficiency",
            "Constraint Satisfaction", "Logical Deductions", "Truth-Teller Problems",
            "Binary Logic", "Network Logic", "Multi-Condition Ordering",
            "Advanced Series Completion", "Advanced Cause & Effect Logic",
        ),
    },
    "Verbal Ability": {
        "Beginner": (
            "Synonyms", "Antonyms", "Fill in the Blanks", "Sentence Completion",
            "Basic Grammar", "Articles", "Prepositions", "Vocabulary in Context",
            "Spelling", "One-Word Substitution", "Word Analogy", "Subject-Verb Agreement",
            "Tenses & Conditionals", "Prepositions & Conjunctions", "Articles & Modifiers",
            "Spelling & Word Choice",
        ),
        "Intermediate": (
            "Sentence Correction", "Error Spotting", "Para Jumbles", "Cloze Test",
            "Idioms & Phrases", "Active & Passive Voice", "Direct & Indirect Speech",
            "Reading Comprehension", "Phrase Replacement", "Word Usage",
            "Sentence Improvement", "Contextual Vocabulary",
            "Contextual Cloze Tests", "Title & Theme Identification",
        ),
        "Advanced": (
            "Inference-Based Reading", "Critical Verbal Reasoning", "Author Tone",
            "Argument Analysis", "Advanced Para Completion", "Passage Summary",
            "Sentence Elimination", "Vocabulary Nuance", "Rhetorical Purpose",
            "Assumption Identification", "Strengthen or Weaken Arguments", "Logical Completion",
            "Advanced Reading Comprehension", "Advanced Sentence Rearrangement",
        ),
    },
    "Analytical Reasoning": {
        "Beginner": (
            "Pattern Recognition", "Simple Data Analysis", "Table Interpretation",
            "Sequence Analysis", "Comparison Problems", "Classification Rules",
            "Basic Caselets", "Simple Arrangements", "Rule Matching", "Observation Skills",
            "Basic Set Analysis", "Visual Data Interpretation", "Logical Puzzles",
            "Critical Thinking",
        ),
        "Intermediate": (
            "Data Analysis", "Chart Interpretation",
            "Conditional Reasoning", "Scheduling", "Ranking Analysis", "Matrix Reasoning",
            "Decision Tables", "Intermediate Caselets", "Set Relationships",
            "Trend Analysis", "Multi-Step Classification",
        ),
        "Advanced": (
            "Multi-Source Analysis", "Constraint Optimization", "Complex Data Interpretation",
            "Analytical Inference", "Hypothesis Testing", "Advanced Caselets",
            "Network & Flow Analysis", "Resource Allocation", "Scenario Analysis",
            "Probabilistic Analysis", "Complex Scheduling", "Decision Optimization",
        ),
    },
    "Computer Fundamentals": {
        "Beginner": (
            "Computer Basics", "Operating Systems", "Input & Output Devices",
            "Memory & Storage", "Computer Hardware", "Software Types", "File Systems",
            "Internet Basics", "Networking Basics", "Database Basics", "Cybersecurity Basics",
            "Number Systems & Conversions", "Volatile vs Non-Volatile Storage",
            "Data Unit Quantification", "Network Topologies & Hardware Devices",
        ),
        "Intermediate": (
            "Process Management", "Memory Management", "Computer Architecture",
            "Network Protocols", "IP Addressing", "Relational Databases", "SQL Fundamentals",
            "Data Representation", "Cloud Computing Basics", "Web Technologies",
            "Security Controls", "Software Development Lifecycle",
            "CPU Scheduling Algorithms", "OSI vs TCP/IP Models",
            "Memory Architecture (Cache/Registers/RAM/ROM)", "Process vs Thread",
            "Memory Management & Virtual Memory", "Web Transmission Protocols",
            "Device Identification (IP vs MAC)", "System Software Architecture",
        ),
        "Advanced": (
            "Operating System Internals", "Concurrency & Deadlocks", "Advanced Networking",
            "Database Transactions", "Indexing & Query Optimization", "Distributed Systems",
            "Computer Organization", "Virtualization", "Cloud Architecture",
            "Cryptography Fundamentals", "System Security", "Performance & Scalability",
            "Advanced CPU Scheduling Algorithms", "Advanced OSI vs TCP/IP Models",
            "Advanced Memory Architecture",
        ),
    },
    "Technical Aptitude": {
        "Beginner": (
            "Programming Fundamentals", "Variables & Data Types", "Operators & Expressions",
            "Conditional Statements", "Loops", "Functions", "Arrays", "Strings",
            "Basic Algorithms", "Debugging Basics", "Object-Oriented Basics", "Code Tracing",
            "Data Structures and Algorithms", "SQL Queries & Joins", "OOP Four Pillars",
            "Flowcharts", "Pseudocode", "Output Prediction",
        ),
        "Intermediate": (
            "Data Structures", "Searching Algorithms", "Sorting Algorithms", "Recursion",
            "Object-Oriented Programming", "Exception Handling", "Time Complexity",
            "Stacks & Queues", "Linked Lists", "Trees", "Hashing", "Database Programming",
            "Searching & Sorting Algorithms", "SQL Queries & Joins", "OOP Four Pillars",
            "Asymptotic Notation", "Database Normalization", "ACID Properties",
            "Keys & Relationships", "Constructors/Destructors/Garbage Collection",
        ),
        "Advanced": (
            "Advanced Data Structures", "Graph Algorithms", "Dynamic Programming",
            "Greedy Algorithms", "Advanced Complexity Analysis", "Concurrency",
            "Design Patterns", "System Design Fundamentals", "Memory Management in Programs",
            "Advanced Recursion", "Algorithm Optimization", "API Design",
            "Advanced Data Structures and Algorithms", "Advanced Searching & Sorting Algorithms",
            "Advanced SQL Queries & Joins", "Advanced OOP Four Pillars",
        ),
    },
}


# Priority is metadata, not part of the public topic label sent to Groq.
PRIORITY_TOPICS = {
    "Quantitative Aptitude": frozenset({
        "Percentages", "Ratio & Proportion", "Profit & Loss", "Discounts",
        "Time & Work", "Time & Distance", "Number Series & Patterns",
        "Time & Work Applications", "Time, Speed & Distance Applications",
        "Advanced Time & Work", "Advanced Time, Speed & Distance",
    }),
    "Logical Reasoning": frozenset({
        "Coding-Decoding", "Blood Relations", "Direction Sense", "Series Completion",
        "Data Sufficiency", "Cause & Effect Logic", "Advanced Data Sufficiency",
        "Advanced Series Completion", "Advanced Cause & Effect Logic",
    }),
    "Verbal Ability": frozenset({
        "Subject-Verb Agreement", "Para Jumbles", "Reading Comprehension",
        "Inference-Based Reading", "Advanced Reading Comprehension",
        "Advanced Sentence Rearrangement",
    }),
    "Analytical Reasoning": frozenset({
        "Pattern Recognition", "Logical Puzzles", "Critical Thinking", "Matrix Reasoning",
    }),
    "Computer Fundamentals": frozenset({
        "CPU Scheduling Algorithms", "OSI vs TCP/IP Models",
        "Memory Architecture (Cache/Registers/RAM/ROM)", "Number Systems & Conversions",
        "Advanced CPU Scheduling Algorithms", "Advanced OSI vs TCP/IP Models",
        "Advanced Memory Architecture",
    }),
    "Technical Aptitude": frozenset({
        "Data Structures and Algorithms", "Searching & Sorting Algorithms",
        "SQL Queries & Joins", "OOP Four Pillars",
        "Advanced Data Structures and Algorithms", "Advanced Searching & Sorting Algorithms",
        "Advanced SQL Queries & Joins", "Advanced OOP Four Pillars",
    }),
}


CATEGORY_TOPIC_CONFIG = {
    category: {
        level: tuple(
            {"name": name, "is_starred": name in PRIORITY_TOPICS[category]}
            for name in names
        )
        for level, names in levels.items()
    }
    for category, levels in _TOPIC_NAMES_BY_LEVEL.items()
}

# Compatibility view for callers that only need labels. New selection logic
# consumes CATEGORY_TOPIC_CONFIG so the priority flag remains authoritative.
CATEGORY_PRACTICE_TOPICS = {
    category: {
        level: tuple(item["name"] for item in definitions)
        for level, definitions in levels.items()
    }
    for category, levels in CATEGORY_TOPIC_CONFIG.items()
}


def topics_for(category, level):
    """Return the immutable eligible topic pool for a category and level."""
    try:
        return CATEGORY_PRACTICE_TOPICS[category][level]
    except KeyError as exc:
        raise ValueError(f"No Category Practice topics configured for {category!r} at {level!r}") from exc


def topic_definitions_for(category,level=None):
    """Return structured topic metadata for one level or the whole category."""
    try:
        levels=CATEGORY_TOPIC_CONFIG[category]
        if level is not None:
            return levels[level]
    except KeyError as exc:
        raise ValueError(f"No topics configured for {category!r} at {level!r}") from exc
    seen=set();merged=[]
    for configured_level in PRACTICE_LEVELS:
        for item in levels[configured_level]:
            key=item["name"].casefold()
            if key not in seen:
                merged.append(item);seen.add(key)
    return tuple(merged)


def topic_is_starred(category,topic):
    return str(topic).strip().casefold() in {
        name.casefold() for name in PRIORITY_TOPICS.get(category,())
    }


def select_weighted_topic_names(definitions,previous_topics,count,rng):
    """Select without replacement using a 50/50 priority-bucket draw.

    Previous non-starred topics are placed behind fresh non-starred topics.
    Starred topics deliberately ignore attempt history so important concepts
    remain available for reinforcement. Neither rule changes the probability
    of choosing the starred versus non-starred bucket.
    """
    if count<1:
        raise ValueError("At least one topic is required")
    unique={}
    for item in definitions:
        name=str(item.get("name") or "").strip()
        if name:
            unique.setdefault(name.casefold(),{"name":name,"is_starred":bool(item.get("is_starred"))})
    if not unique:
        raise ValueError("Topic pool is empty")
    previous={str(topic).strip().casefold() for topic in previous_topics or ()}
    buckets={True:{"fresh":[],"recent":[]},False:{"fresh":[],"recent":[]}}
    for key,item in unique.items():
        destination="recent" if not item["is_starred"] and key in previous else "fresh"
        buckets[item["is_starred"]][destination].append(item["name"])
    for bucket in buckets.values():
        rng.shuffle(bucket["fresh"]);rng.shuffle(bucket["recent"])

    selected=[]
    while len(selected)<count:
        preferred=rng.random()<.5
        preferred_source=buckets[preferred]["fresh"] or buckets[preferred]["recent"]
        alternate_source=buckets[not preferred]["fresh"] or buckets[not preferred]["recent"]
        source=preferred_source or alternate_source
        if source:
            selected.append(source.pop())
            continue
        # Repetition is only needed when the complete category pool is smaller
        # than the requested test. Current production pools are larger than the
        # maximum session, so normal Mixed and Category Practice schedules are
        # unique while preserving bucket-level weighting.
        choices=[item["name"] for item in unique.values()]
        non_adjacent=[name for name in choices if not selected or name!=selected[-1]]
        selected.append(rng.choice(non_adjacent or choices))
    return selected


def select_rotating_topic_names(definitions,previous_topics,count,rng):
    """Select topics uniformly while placing all recently used topics last.

    This policy is used by Mixed Test. Priority metadata is deliberately
    ignored: every configured topic has the same chance within the fresh
    pool, and every topic participates in the same rotation rule.
    """
    if count<1:
        raise ValueError("At least one topic is required")
    unique={}
    for item in definitions:
        name=str(item.get("name") or "").strip()
        if name:
            unique.setdefault(name.casefold(),name)
    if not unique:
        raise ValueError("Topic pool is empty")
    previous={str(topic).strip().casefold() for topic in previous_topics or ()}
    fresh=[name for key,name in unique.items() if key not in previous]
    recent=[name for key,name in unique.items() if key in previous]
    rng.shuffle(fresh);rng.shuffle(recent)
    selected=(fresh+recent)[:count]
    while len(selected)<count:
        choices=list(unique.values())
        non_adjacent=[name for name in choices if not selected or name!=selected[-1]]
        selected.append(rng.choice(non_adjacent or choices))
    return selected


def validate_topic_config(minimum_topics=5):
    """Fail fast when a category/level taxonomy is incomplete or duplicated."""
    for category, levels in CATEGORY_PRACTICE_TOPICS.items():
        if set(levels) != set(PRACTICE_LEVELS):
            raise ValueError(f"{category} must define all practice levels")
        for level, topics in levels.items():
            if len(topics) < minimum_topics:
                raise ValueError(f"{category}/{level} needs at least {minimum_topics} topics")
            if len({topic.casefold() for topic in topics}) != len(topics):
                raise ValueError(f"{category}/{level} contains duplicate topic labels")
            definitions=CATEGORY_TOPIC_CONFIG[category][level]
            if any(set(item)!={"name","is_starred"} for item in definitions):
                raise ValueError(f"{category}/{level} has invalid topic metadata")


validate_topic_config()
