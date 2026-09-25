import unittest
from unittest.mock import MagicMock, patch

from job_agent.skills import (
    extract_skills_from_job,
    extract_skills_from_text,
    extract_skills_from_user_message,
)
from job_agent.chat_service import format_job_listings_markdown, _detect_message_profile_updates


class SkillsAndFormattingTests(unittest.TestCase):
    def test_extract_skills_from_text(self):
        sample_jd = (
            "We are seeking a Junior Software Engineer with solid foundation in "
            "Python, Django, PostgreSQL, Docker and AWS. Knowledge of React or TypeScript is a plus."
        )
        skills = extract_skills_from_text(sample_jd)
        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertIn("Docker", skills)
        self.assertIn("AWS", skills)
        self.assertIn("React", skills)
        self.assertIn("TypeScript", skills)

    def test_extract_skills_from_user_message(self):
        msg1 = "My skills are Python, React and MySQL"
        skills1 = extract_skills_from_user_message(msg1)
        self.assertEqual(set(skills1), {"Python", "React", "MySQL"})

        msg2 = "I updated my skills: Java, Spring Boot, Docker"
        skills2 = extract_skills_from_user_message(msg2)
        self.assertEqual(set(skills2), {"Java", "Spring Boot", "Docker"})

        msg3 = "I know Node.js, MongoDB, Express and AWS"
        skills3 = extract_skills_from_user_message(msg3)
        self.assertIn("Node.js", skills3)
        self.assertIn("MongoDB", skills3)
        self.assertIn("Express.js", skills3)
        self.assertIn("AWS", skills3)

    def test_extract_skills_from_job(self):
        job_with_empty_skills = {
            "title": "Backend Python Developer",
            "department": "Engineering",
            "description": "Develop scalable APIs using FastAPI and SQL databases. Deploy on Docker.",
            "skills": "[]",
        }
        extracted = extract_skills_from_job(job_with_empty_skills)
        self.assertIn("Python", extracted)
        self.assertIn("FastAPI", extracted)
        self.assertIn("SQL", extracted)
        self.assertIn("Docker", extracted)

    def test_detect_message_profile_updates(self):
        msg = "My skills are React and TypeScript, and I want jobs in Chennai or Remote"
        updates = _detect_message_profile_updates(msg)
        self.assertIn("React", updates.get("skills_to_add", []))
        self.assertIn("TypeScript", updates.get("skills_to_add", []))
        self.assertIn("Chennai", updates.get("locations_to_set", []))
        self.assertIn("Remote", updates.get("locations_to_set", []))

    def test_format_job_listings_markdown(self):
        mock_jobs = [
            {
                "id": 101,
                "title": "Junior Python Engineer",
                "company": "TechCorp",
                "location": "Chennai",
                "seniority_tier": "entry",
                "trust_badge": "🛡️ Verified Corporate Posting",
                "trust_score": 95,
                "match_score": 92,
                "salary_text": "₹4.5 - ₹6.5 LPA",
                "experience_min": 0,
                "experience_max": 2,
                "skills": ["Python", "SQL", "Git"],
                "apply_url": "https://boards.greenhouse.io/techcorp/jobs/101",
            }
        ]
        markdown = format_job_listings_markdown(mock_jobs, intro="Here are your matches")
        self.assertIn("1. **Junior Python Engineer** @ **TechCorp** (Chennai)", markdown)
        self.assertIn("🎓 [Entry-Level / Fresher]", markdown)
        self.assertIn("Match 92%", markdown)
        self.assertIn("🛡️ Verified Corporate Posting", markdown)
        self.assertIn("95% Trust", markdown)
        self.assertIn("₹4.5 - ₹6.5 LPA", markdown)
        self.assertIn("Python, SQL, Git", markdown)
        self.assertIn("[Apply on Official Portal ↗](https://boards.greenhouse.io/techcorp/jobs/101)", markdown)


if __name__ == "__main__":
    unittest.main()
