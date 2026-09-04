"""Authoritative local answer scoring for learner assessments."""


def evaluate_answer(question, selected):
    """Score against the stored answer key without any provider call."""
    return selected == question.correct_answer, "authoritative"
