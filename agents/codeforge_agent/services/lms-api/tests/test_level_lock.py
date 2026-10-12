"""A learner practises their own level; levels above it stay locked until
they finish the one they are on, and finished levels stay open."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standalone_workflow import COURSE, PROBLEM, TECH, FakeJudge, FakeRepository  # noqa: E402
from lms_api.app import create_app  # noqa: E402
from lms_api.evaluation import EvaluationService  # noqa: E402

SUMMARY = {"description": "", "max_score": 100, "language": "python", "question_type": "code", "sequence": 1,
           "progress": "Not Started", "best_score": 0, "attempts": 0, "topic_slug": "print-and-input", "topic_name": "Print and Input"}
EASY = {**SUMMARY, "id": 1, "name": "Add Two Numbers", "slug": "add-two-numbers", "difficulty": "Easy"}
MEDIUM = {**SUMMARY, "id": 2, "name": "Word Count", "slug": "word-count", "difficulty": "Medium"}
HARD = {**SUMMARY, "id": 3, "name": "Matrix Path", "slug": "matrix-path", "difficulty": "Hard"}


class LevelRepository(FakeRepository):
    def list_level_problems(self, student_id, course_slug, technology_slug, difficulty):
        del student_id
        self.list_technologies(course_slug)
        return COURSE, TECH, [p for p in (EASY, MEDIUM, HARD) if p["difficulty"] == difficulty]

    def problem_set(self, student_id, technology_slug=None):
        del student_id, technology_slug
        languages = [{"slug": "python", "name": "Python", "course_slug": COURSE["slug"],
                      "counts": {"Easy": {"total": 1, "solved": 0}, "Medium": {"total": 1, "solved": 0}, "Hard": {"total": 1, "solved": 0}}}]
        return languages, "python", COURSE["slug"], [{**p, "number": i + 1} for i, p in enumerate((EASY, MEDIUM, HARD))]

    def problem_for_evaluation(self, student_id, problem_id):
        del student_id
        return {1: PROBLEM, 2: {**PROBLEM, "id": 2, "difficulty": "Medium"}, 3: {**PROBLEM, "id": 3, "difficulty": "Hard"}}.get(problem_id)

    def get_problem(self, student_id, course_slug, technology_slug, topic_slug, problem_slug):
        del student_id, course_slug, technology_slug
        return COURSE, TECH, {"slug": topic_slug}, next(p for p in (EASY, MEDIUM, HARD) if p["slug"] == problem_slug)


CODE = "a, b = map(int, input().split())\nprint(a + b)"


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

    def test_the_problem_set_locks_the_levels_above_the_learners(self):
        response = self.invoke("problem_set", {"technology_slug": "python"}, "easy")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["level_name"], "Beginner")
        self.assertEqual([(p["number"], p["difficulty"], p["locked"]) for p in response.json["problems"]],
                         [(1, "Easy", False), (2, "Medium", True), (3, "Hard", True)])
        medium = self.invoke("problem_set", {}, "medium").json["problems"]
        self.assertEqual([p["locked"] for p in medium], [False, False, True])

    def test_the_level_list_shows_only_the_learners_level(self):
        response = self.invoke("list_level_problems", {"course_slug": COURSE["slug"], "technology_slug": "python", "difficulty": "hard"}, "easy")
        self.assertEqual(response.json["difficulty"], "Easy")
        self.assertEqual([p["difficulty"] for p in response.json["problems"]], ["Easy"])

    def test_a_higher_level_cannot_be_opened_or_submitted_but_a_finished_one_can(self):
        opened = self.invoke("get_problem", {"course_slug": COURSE["slug"], "technology_slug": "python",
                                             "topic_slug": "print-and-input", "problem_slug": "word-count"}, "easy")
        self.assertEqual(opened.status_code, 403)
        self.assertEqual(opened.json["error"]["code"], "level_locked")
        self.assertIn("solve every Easy problem", opened.json["error"]["message"])
        self.assertEqual(self.invoke("submit_problem", {"problem_id": 2, "sourceCode": CODE}, "easy").status_code, 403)
        # A Medium learner can still redo Easy problems.
        self.assertEqual(self.invoke("submit_problem", {"problem_id": 1, "sourceCode": CODE}, "medium").status_code, 201)


if __name__ == "__main__":
    unittest.main()
