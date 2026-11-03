"""The same problem with other numbers or nouns reads to a learner as a repeat.

The pairs below were all found together inside one stored test.
"""
import pytest
from flask import Flask

from backend.app.services import test_generation
from backend.app.services.question_validation import questions_share_template

SLOT = {"category": "Logical Reasoning", "topic": "Syllogism", "difficulty": "Medium"}
OPTIONS = {"A": "First", "B": "Second", "C": "Third", "D": "Fourth"}
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

TEA = "In a group of 100 people, 60 like tea, 40 like coffee, and 10 like both. How many like only tea?"
CHOCOLATE = "In a group of 150 people, 90 like chocolate, 70 like vanilla, and 30 like both. How many like only vanilla?"
CHAIRS = "In a row of five chairs, Meera sits left of Ravi and right of Tara. Who sits in the middle position?"


@pytest.mark.parametrize("left,right", [
    (TEA, CHOCOLATE),
    ("How many different ways can 4 books be arranged on a shelf?", "How many ways can you arrange 5 books on a shelf?"),
    ("In a survey of 50 people, 30 like coffee, 20 like tea, and 10 like both. How many like only coffee?",
     "In a survey of 100 people, 70 like dogs, 50 like cats, and 30 like both. How many like only dogs?"),
    ("A train travels 60 km in 1 hour. How far will it travel in 2.5 hours?",
     "A train travels 45 km in 1 hour. How far will it travel in 4 hours?"),
    ("What is the binary equivalent of the decimal number 10?", "What is the binary representation of the decimal number 13?"),
    ("All cats are mammals. Some mammals are not dogs. Therefore, some cats are not dogs. Is this conclusion valid?",
     "If all cats are mammals and some mammals are not dogs, can we conclude that some cats are not dogs?"),
])
def test_the_same_problem_is_recognised(left, right):
    assert questions_share_template(left, right)


@pytest.mark.parametrize("left,right", [
    ("What is the primary purpose of a firewall in a computer network?", "What is the primary purpose of a load balancer in a system design?"),
    ("What is the LCM of 12 and 15?", "What is the value of log10(100)?"),
    ("What is the area of a triangle with a base of 6 units and a height of 4 units?", "What is the volume of a cylinder with a radius of 3 cm and a height of 5 cm?"),
    ("Which of the following is NOT an ACID property?", "Which of the following is a primary function of an operating system?"),
    # Worded alike by nature: the numbers are the question.
    ("What is the next number in the series 2, 4, 8, 16?", "What is the next number in the series 3, 6, 12, 24?"),
    # Code questions share their boilerplate.
    ("What will be the output of the following Python code? `x = [1, 2]; print(x[0])`",
     "What will be the output of the following Python code? `for i in range(5): print(i)`"),
])
def test_different_problems_are_left_alone(left, right):
    assert not questions_share_template(left, right)


def good(question):
    return {**SLOT, "question": question, "options": dict(OPTIONS), "correct_answer": "A",
            "explanation": "The stated rule shows that the correct option is A."}


class Provider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.asked_for = []

    def __call__(self, system_prompt, prompt, temperature, **kwargs):
        self.asked_for.append(kwargs["response_schema"]["properties"]["questions"]["minItems"])
        return ({"questions": self.responses[len(self.asked_for) - 1]}, dict(USAGE))


def run(monkeypatch, provider, attempts):
    monkeypatch.setattr(test_generation, "json_completion", provider)
    app = Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-test", ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        return test_generation.generate_questions(
            [dict(SLOT), dict(SLOT)], allow_demo_fallback=False, max_validation_attempts=attempts,
        )[0]


def test_a_reused_template_is_replaced_keeping_the_other_question(monkeypatch):
    provider = Provider([good(TEA), good(CHOCOLATE)], [good(CHAIRS)])
    questions = run(monkeypatch, provider, attempts=3)
    assert [question["question"] for question in questions] == [TEA, CHAIRS]
    assert provider.asked_for == [2, 1]


def test_a_template_that_will_not_go_away_never_fails_the_test(monkeypatch):
    provider = Provider([good(TEA), good(CHOCOLATE)], [good(CHOCOLATE)])
    questions = run(monkeypatch, provider, attempts=2)
    assert [question["question"] for question in questions] == [TEA, CHOCOLATE]
