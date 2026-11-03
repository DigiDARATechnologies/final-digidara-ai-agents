"""The Python Full Stack course covers Flask and React.js, in learning order."""
from lms_api.catalog import COURSE_TECHNOLOGIES, TECHNOLOGIES, TOPICS, slugify
from lms_api.problem_catalog import PROBLEMS


def test_the_course_lists_every_technology_in_learning_order():
    assert COURSE_TECHNOLOGIES["python-full-stack"] == ["html", "css", "javascript", "python", "mysql", "flask", "react"]
    known = {slug for _, slug, *_ in TECHNOLOGIES}
    assert {"flask", "react"} <= known
    assert {"React.js", "Flask"} <= {name for name, *_ in TECHNOLOGIES}


def test_other_courses_are_unchanged():
    assert COURSE_TECHNOLOGIES["data-analytics"] == ["python", "mysql", "pandas", "numpy"]
    assert COURSE_TECHNOLOGIES["generative-agentic-ai"] == ["python"]


def test_every_topic_has_five_valid_questions_at_each_level():
    for technology in ("flask", "react"):
        problems = [p for p in PROBLEMS if p["technology"] == technology]
        assert len(problems) == 40
        assert {p["difficulty"] for p in problems} == {"Easy", "Medium", "Hard"}
        for topic in TOPICS[technology]:
            assert sum(p["topic"] == slugify(topic) for p in problems) == 5
        for problem in problems:
            assert problem["question_type"] == "mcq" and len(set(problem["mcq_options"].values())) == 4
            assert problem["mcq_correct_key"] in problem["mcq_options"] and problem["mcq_explanation"]


def test_problem_slugs_stay_unique():
    slugs = [p["slug"] for p in PROBLEMS]
    assert len(slugs) == len(set(slugs))
