"""Jobs are shown only to learners whose degree qualifies for them."""
import pytest

from job_agent.matching import candidate_degree, degree_eligible


def job(description):
    return {"title": "Data Scientist", "description": description}


@pytest.mark.parametrize("description, degree, eligible", [
    ("Bachelor's degree in Computer Science or related field.", "b.sc", True),
    ("Master's degree in Statistics required.", "b.sc", False),
    ("Master's degree in Statistics required.", "m.sc", True),
    ("Bachelor's degree required. Master's preferred.", "b.sc", True),
    ("B.E / B.Tech in CSE, ECE.", "b.sc", False),
    ("B.E / B.Tech in CSE, ECE.", "b.tech ai&ds", True),
    ("B.E / B.Tech in CSE, ECE.", "m.sc", False),
    ("No degree mentioned, just Python skills.", "diploma", True),
    ("PhD in Machine Learning.", "m.sc", False),
    ("Any degree. Freshers welcome.", "b.com", True),
    ("Diploma or any graduate can apply", "diploma", True),
    ("A degree in computer science.", "diploma", False),
    ("Masters in Data Science, M.Tech or MCA.", "b.tech", False),
    ("Work with MS Office and Excel.", "diploma", True),
])
def test_degree_decides_eligibility(description, degree, eligible):
    assert degree_eligible(job(description), degree) is eligible


def test_an_unknown_degree_sees_every_job():
    assert candidate_degree("") == (None, False)
    assert degree_eligible(job("Master's degree required."), "")


def test_degree_text_is_read_as_a_level():
    assert candidate_degree("m.sc")[0] == candidate_degree("mca")[0] == 3
    assert candidate_degree("b.e cse") == (2, True)
    assert candidate_degree("diploma")[0] == 1
