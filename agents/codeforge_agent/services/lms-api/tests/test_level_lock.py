"""A learner practises only the problems of their own Coding level."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standalone_workflow import COURSE, TECH, FakeJudge, FakeRepository  # noqa: E402
from lms_api.app import create_app  # noqa: E402
from lms_api.evaluation import EvaluationService  # noqa: E402

MEDIUM = {"id": 2, "name": "Word Count", "slug": "word-count", "description": "Count", "difficulty": "Medium", "max_score": 100,
          "language": "python", "sequence": 1, "progress": "Not Started", "best_score": 0, "attempts": 0}


class LevelRepository(FakeRepository):
    def list_level_problems(self, student_id, course_slug, technology_slug, difficulty):
        del student_id
        self.list_technologies(course_slug)
        easy = {**MEDIUM, "id": 1, "name": "Add Two Numbers", "slug": "add-two-numbers", "difficulty": "Easy"}
        rows = [{**p, "topic_slug": "print-and-input", "topic_name": "Print and Input"} for p in (easy, MEDIUM)]
        return COURSE, TECH, [row for row in rows if row["difficulty"] == difficulty]

    def get_problem(self, student_id, course_slug, technology_slug, topic_slug, problem_slug):
        course, technology, topic, problems = self.list_problems(student_id, course_slug, technology_slug, topic_slug)
        return course, technology, topic, next(p for p in problems if p["slug"] == problem_slug)


class LevelLockTests(unittest.TestCase):
    def setUp(self):
        self.repo = LevelRepository()
        self.app = create_app({"TESTING": True, "LMS_API_SHARED_SECRET": "s", "CODING_PRACTICE_ENABLED": True}, self.repo)
        self.app.extensions["evaluation"] = EvaluationService(self.repo, FakeJudge())
        self.client = self.app.test_client()

    def invoke(self, action, payload, level=None):
        body = {"action": action, "payload": {"sessionToken": "valid-session", **payload}}
        if level:
            body["learner"] = {"difficulty": level}
        return self.client.post("/api/invoke", json=body)

    def test_the_list_shows_only_the_learners_level_across_topics(self):
        response = self.invoke("list_level_problems", {"course_slug": COURSE["slug"], "technology_slug": "python"}, "easy")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["difficulty"], "Easy")
        self.assertEqual([p["difficulty"] for p in response.json["problems"]], ["Easy"])
        self.assertEqual(response.json["problems"][0]["topic_slug"], "print-and-input")
        # The level comes from the gateway's learner context, not the browser.
        sneaky = self.invoke("list_level_problems", {"course_slug": COURSE["slug"], "technology_slug": "python", "difficulty": "hard"}, "easy")
        self.assertEqual(sneaky.json["difficulty"], "Easy")

    def test_another_levels_problem_cannot_be_opened_or_submitted(self):
        opened = self.invoke("get_problem", {"course_slug": COURSE["slug"], "technology_slug": "python",
                                             "topic_slug": "print-and-input", "problem_slug": "add-two-numbers"}, "medium")
        self.assertEqual(opened.status_code, 403)
        self.assertEqual(opened.json["error"]["code"], "level_locked")
        self.assertIn("Your Coding level is Medium", opened.json["error"]["message"])
        submitted = self.invoke("submit_problem", {"problem_id": 1, "sourceCode": "a, b = map(int, input().split())\nprint(a + b)"}, "medium")
        self.assertEqual(submitted.status_code, 403)
        ok = self.invoke("submit_problem", {"problem_id": 1, "sourceCode": "a, b = map(int, input().split())\nprint(a + b)"}, "easy")
        self.assertEqual(ok.status_code, 201)


if __name__ == "__main__":
    unittest.main()
