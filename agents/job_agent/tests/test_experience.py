import unittest
from job_agent.experience import (
    classify_job_seniority,
    extract_experience_from_text,
    format_experience_badge,
    is_fresher_eligible,
)


class ExperienceClassificationUnitTests(unittest.TestCase):
    def test_extract_experience_ranges_and_minimums(self):
        # Explicit ranges
        self.assertEqual(extract_experience_from_text("Python Dev (3-6 years)"), (3.0, 6.0))
        self.assertEqual(extract_experience_from_text("SDE", "Experience required: 4 to 8 yrs in backend"), (4.0, 8.0))
        self.assertEqual(extract_experience_from_text("Fullstack Developer", "Exp: 5.1-7 years"), (5.1, 7.0))

        # Minimum requirements
        self.assertEqual(extract_experience_from_text("Java Dev", "Minimum 5 years of hands-on experience in AWS"), (5.0, None))
        self.assertEqual(extract_experience_from_text("React Dev", "At least 3 years experience"), (3.0, None))
        self.assertEqual(extract_experience_from_text("Cloud Engineer", "Requires 4+ years of experience"), (4.0, None))

        # Fresher indicators
        self.assertEqual(extract_experience_from_text("Junior Python Developer", "Freshers welcome"), (0.0, 1.0))
        self.assertEqual(extract_experience_from_text("Software Intern", "0-1 years"), (0.0, 1.0))
        self.assertEqual(extract_experience_from_text("Graduate Engineer Trainee"), (0.0, 1.0))

    def test_classify_job_seniority_eliminates_false_entry_defaults(self):
        # Plain generic title with NO experience mentioned -> MUST NOT default to entry!
        plain_job = {"title": "Software Engineer", "description": "Working on microservices architecture"}
        self.assertEqual(classify_job_seniority(plain_job), "growth")

        plain_py = {"title": "Python Developer", "description": "Develop APIs using FastAPI"}
        self.assertEqual(classify_job_seniority(plain_py), "growth")

        # Senior and Roman numeral titles
        sde3 = {"title": "System Dev Engineer III", "description": "Lead platform architecture"}
        self.assertEqual(classify_job_seniority(sde3), "senior")

        sde2 = {"title": "SDE II - Backend", "description": "Mid-level backend work"}
        self.assertEqual(classify_job_seniority(sde2), "senior")

        lead = {"title": "Lead Full Stack Developer", "description": "Lead a team of developers"}
        self.assertEqual(classify_job_seniority(lead), "senior")

        # Descriptions with senior keywords
        mentor_job = {
            "title": "Data Scientist - AI/ML",
            "description": "Senior-level position responsible for mentoring junior engineers and leading AI design",
        }
        self.assertEqual(classify_job_seniority(mentor_job), "senior")

        # Real Virtusa 8-12 yr job
        virtusa_job = {
            "title": "Python Developer",
            "description": "Candidates must have 8.0 to 12.0 years of experience in enterprise development",
        }
        self.assertEqual(classify_job_seniority(virtusa_job), "senior")

        # True fresher jobs
        jr_node = {"title": "Junior Node.js Developer", "description": "Good foundation in JavaScript"}
        self.assertEqual(classify_job_seniority(jr_node), "entry")

        fresher_get = {"title": "Graduate Engineer Trainee", "description": "2024 / 2025 college graduates"}
        self.assertEqual(classify_job_seniority(fresher_get), "entry")

        intern = {"title": "React Native Intern", "description": "Looking for college interns"}
        self.assertEqual(classify_job_seniority(intern), "entry")

    def test_is_fresher_eligible(self):
        # True fresher
        self.assertTrue(is_fresher_eligible({"title": "Junior Software Engineer", "experience_min": 0}))
        self.assertTrue(is_fresher_eligible({"title": "Frontend Intern", "description": "Freshers can apply"}))

        # Disqualified
        self.assertFalse(is_fresher_eligible({"title": "Software Engineer", "experience_min": 4}))
        self.assertFalse(is_fresher_eligible({"title": "Lead Developer", "description": "Freshers welcome"}))  # Lead disqualifies
        self.assertFalse(is_fresher_eligible({"title": "Senior SW Engineer", "experience_min": 0}))  # Senior disqualifies
        self.assertFalse(is_fresher_eligible({"title": "Software Engineer"}))  # Generic plain title without fresher proof is false

    def test_format_experience_badge(self):
        self.assertEqual(format_experience_badge({"experience_min": 0, "experience_max": 1}), "🎓 Fresher (0–1 yrs)")
        self.assertEqual(format_experience_badge({"experience_min": 3, "experience_max": 6}), "💼 3–6 yrs")
        self.assertEqual(format_experience_badge({"experience_min": 5, "experience_max": None}), "💼 5+ yrs")


if __name__ == "__main__":
    unittest.main()
