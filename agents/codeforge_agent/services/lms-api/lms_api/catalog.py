COURSES = [
    ("Data Analytics", "data-analytics", "Build practical skills for cleaning, querying, and explaining data.", "chart", 1),
    ("Data Science", "data-science", "Develop a strong foundation for data preparation and scientific computing.", "data", 2),
    ("AI and Machine Learning", "ai-machine-learning", "Prepare the Python and numerical foundations used in machine learning.", "brain", 3),
    ("Generative AI and Agentic AI", "generative-agentic-ai", "Strengthen the Python foundations behind modern AI applications.", "spark", 4),
    ("Python Full Stack Development", "python-full-stack", "Practice backend, database, and browser technologies used in full-stack projects.", "layers", 5),
]

TECHNOLOGIES = [
    ("Python", "python", "Learn Python syntax, data structures, functions, files, errors, and objects.", "PY", 1),
    ("MySQL", "mysql", "Learn relational querying, aggregation, joins, constraints, and indexes.", "SQL", 2),
    ("HTML", "html", "Build accessible, semantic document structures for the web.", "HTML", 3),
    ("CSS", "css", "Style responsive interfaces with modern layout and visual techniques.", "CSS", 4),
    ("JavaScript", "javascript", "Add browser behavior, data handling, events, and asynchronous workflows.", "JS", 5),
    ("Pandas", "pandas", "Clean, reshape, combine, and summarize tabular data in Python.", "PD", 6),
    ("NumPy", "numpy", "Work efficiently with numerical arrays, broadcasting, and matrix operations.", "NP", 7),
]

COURSE_TECHNOLOGIES = {
    "data-analytics": ["python", "mysql", "pandas", "numpy"],
    "data-science": ["python", "mysql", "pandas", "numpy"],
    "ai-machine-learning": ["python", "pandas", "numpy"],
    "generative-agentic-ai": ["python"],
    "python-full-stack": ["python", "mysql", "html", "css", "javascript"],
}

TOPICS = {
    "python": [
        "Introduction and Syntax", "Print and Input", "Variables", "Data Types", "Type Conversion",
        "Operators", "Conditions", "Loops", "Strings", "Lists", "Tuples", "Sets", "Dictionaries",
        "Functions", "Lambda Functions", "File Handling", "Exception Handling",
        "Object-Oriented Programming", "Modules and Packages", "Debugging",
    ],
    "mysql": [
        "SQL Syntax", "Databases and Tables", "SELECT", "WHERE", "ORDER BY", "LIMIT",
        "Aggregate Functions", "GROUP BY", "HAVING", "Joins", "Subqueries",
        "Common Table Expressions", "Window Functions", "INSERT", "UPDATE", "DELETE",
        "Constraints", "Views", "Index Fundamentals",
    ],
    "html": [
        "Document Structure", "Headings and Paragraphs", "Links", "Images", "Lists", "Tables",
        "Forms", "Semantic Elements", "Audio and Video", "Accessibility Fundamentals",
    ],
    "css": [
        "Selectors", "Colors", "Typography", "Box Model", "Display", "Position", "Flexbox", "Grid",
        "Responsive Design", "Media Queries", "Transitions", "Animations",
    ],
    "javascript": [
        "Syntax", "Variables", "Data Types", "Operators", "Conditions", "Loops", "Functions", "Arrays",
        "Objects", "String Methods", "Array Methods", "DOM Manipulation", "Events", "Form Validation",
        "Promises", "Async/Await", "Fetch API", "Error Handling",
    ],
    "pandas": [
        "Series", "DataFrames", "Reading CSV Files", "Selecting Rows and Columns", "Filtering",
        "Missing Values", "Duplicate Handling", "Data-Type Conversion", "Sorting", "Grouping",
        "Aggregation", "Merging", "Joining", "Pivot Tables", "Date and Time Operations", "Data Cleaning",
    ],
    "numpy": [
        "Array Introduction", "Array Creation", "Dimensions and Shapes", "Indexing", "Slicing", "Data Types",
        "Reshaping", "Broadcasting", "Mathematical Operations", "Aggregation", "Boolean Filtering",
        "Random Operations", "Matrix Operations",
    ],
}


def slugify(value):
    return "-".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )


def topic_description(technology, topic):
    return f"Understand {topic.lower()} in {technology} and recognize when to apply it in practical code."


def objectives(technology, topic):
    return [f"Explain the purpose of {topic.lower()} in {technology}.", f"Recognize the core syntax and common use cases for {topic.lower()}."]
