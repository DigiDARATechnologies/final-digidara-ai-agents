import learner_context


def _with(learner):
    return learner_context.set_from_envelope({"learner": learner})


def test_own_skills_lead_a_role_interview_for_the_target_role():
    token = _with({"target_role": "Python Developer", "skills": ["Python", "Django", "python", "SQL"]})
    try:
        assert learner_context.own_skills_for("python  developer") == ["python", "django", "sql"]
        assert learner_context.own_skills_for("Data Analyst") == []
    finally:
        learner_context.reset(token)


def test_no_learner_means_no_own_skills():
    token = _with(None)
    try:
        assert learner_context.own_skills_for("Python Developer") == []
    finally:
        learner_context.reset(token)
