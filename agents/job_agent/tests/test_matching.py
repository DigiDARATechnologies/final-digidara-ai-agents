import unittest

from job_agent.matching import parse_list, score_job


class MatchingTests(unittest.TestCase):
    def test_parse_list_accepts_json_and_delimited_values(self):
        self.assertEqual(parse_list('["Python", "SQL"]'), ["Python", "SQL"])
        self.assertEqual(parse_list("Python, Flask; SQL"), ["Python", "Flask", "SQL"])

    def test_verified_and_preferred_matches_are_explained(self):
        job = {
            "title": "Python Developer",
            "location": "Chennai",
            "work_mode": "hybrid",
            "skills": ["Python", "Flask", "SQL"],
            "experience_min": 0,
        }
        profile = {
            "skills": ["Python", "Flask", "SQL"],
            "preferred_titles": ["Python Developer"],
            "preferred_locations": ["Chennai"],
            "preferred_work_mode": "hybrid",
            "experience_years": 0,
        }
        score, reasons = score_job(job, profile, "Python Full Stack")
        self.assertGreaterEqual(score, 70)
        self.assertTrue(any("Skills from your preferred roles" in reason for reason in reasons))
        self.assertIn("Matches your preferred role", reasons)


class CategoryScoringTests(unittest.TestCase):
    """A Python course is foundational for Data Analyst/Data Scientist/AI-ML
    roles ("broader relevant jobs"), so those should score above unrelated
    jobs but below an exact Python Full Stack match - and Digital Marketing
    must never benefit, since it shares no technical skill base."""

    empty_profile = {
        "skills": [], "preferred_titles": [], "preferred_locations": [],
        "preferred_work_mode": "", "experience_years": 0,
    }

    def test_exact_category_match_outscores_related_match(self):
        exact_job = {"title": "Python Full Stack Developer", "location": "", "work_mode": "", "skills": []}
        related_job = {"title": "Data Analyst", "location": "", "work_mode": "", "skills": []}

        exact_score, exact_reasons = score_job(exact_job, self.empty_profile, "Python")
        related_score, related_reasons = score_job(related_job, self.empty_profile, "Python")

        self.assertGreater(exact_score, related_score)
        self.assertTrue(any("Matches your preferred role category" in r for r in exact_reasons))
        self.assertTrue(any("Related to your preferred role category" in r for r in related_reasons))

    def test_related_match_outscores_unrelated_job(self):
        related_job = {"title": "Data Scientist", "location": "", "work_mode": "", "skills": []}
        unrelated_job = {"title": "Digital Marketing Specialist", "location": "", "work_mode": "", "skills": []}

        related_score, related_reasons = score_job(related_job, self.empty_profile, "Python")
        unrelated_score, unrelated_reasons = score_job(unrelated_job, self.empty_profile, "Python")

        self.assertGreater(related_score, unrelated_score)
        self.assertFalse(any("preferred role category" in r for r in unrelated_reasons))

    def test_digital_marketing_course_never_gets_a_python_boost(self):
        # Sanity check the isolation holds in both directions.
        python_job = {"title": "Python Developer", "location": "", "work_mode": "", "skills": []}
        score, reasons = score_job(python_job, self.empty_profile, "Digital Marketing")
        self.assertFalse(any("preferred role category" in r for r in reasons))

    def test_job_category_field_is_used_when_already_stored(self):
        # When a job dict already has a `category` (as every real DB row
        # does), that stored value should be used directly rather than
        # re-classifying from title text.
        job = {"title": "Ambiguous Role Title", "category": "data_analytics", "location": "", "work_mode": "", "skills": []}
        score, reasons = score_job(job, self.empty_profile, "Python")
        self.assertTrue(any("Related to your preferred role category: Data Analytics" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
