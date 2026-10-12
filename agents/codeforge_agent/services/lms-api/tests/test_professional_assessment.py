"""Professional assessments: only for Professional learners, Expert content
only inside the learner's own running attempt, scores recorded, no tutor."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standalone_workflow import PROBLEM, FakeJudge, FakeRepository  # noqa: E402
from lms_api.app import create_app  # noqa: E402
from lms_api.evaluation import EvaluationService  # noqa: E402

EXPERT = {**PROBLEM, "id": 9, "difficulty": "Hard", "track": "professional"}
CODE = "a, b = map(int, input().split())\nprint(a + b)"


class AssessmentRepository(FakeRepository):
    def __init__(self):
        super().__init__()
        self.running = None
        self.recorded = []

    def problem_for_evaluation(self, student_id, problem_id):
        del student_id
        return {1: {**PROBLEM, "track": "practice"}, 9: EXPERT}.get(problem_id)

    def start_assessment(self, student_id, technology_slug, minutes):
        self.running = {"id": 5, "status": "in_progress", "minutes": minutes, "technology": technology_slug,
                        "items": [{"position": 2, "problem_id": 9, "kind": "expert"}]}
        return self.running

    def assessment_item_for(self, student_id, problem_id):
        del student_id
        return {"assessment_id": 5, "position": 2} if self.running and problem_id == 9 else None

    def record_assessment_score(self, assessment_id, position, score):
        self.recorded.append((assessment_id, position, score))

    def get_submission(self, student_id, problem_id, submission_id):
        return {"id": submission_id, "status": "Wrong Answer", "source_code": "", "result_json": []}


class ProfessionalAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.repo = AssessmentRepository()
        self.app = create_app({"TESTING": True, "LMS_API_SHARED_SECRET": "s", "CODING_PRACTICE_ENABLED": True}, self.repo)
        self.app.extensions["evaluation"] = EvaluationService(self.repo, FakeJudge())
        self.client = self.app.test_client()

    def invoke(self, action, payload, level="professional", difficulty="hard"):
        return self.client.post("/api/invoke", json={
            "action": action, "payload": {"sessionToken": "valid-session", **payload},
            "learner": {"level": level, "difficulty": difficulty}})

    def test_only_a_professional_learner_can_start(self):
        refused = self.invoke("start_assessment", {"technology_slug": "python"}, level="hard")
        self.assertEqual(refused.status_code, 403)
        started = self.invoke("start_assessment", {"technology_slug": "python"})
        self.assertEqual(started.status_code, 201)
        self.assertEqual(started.json["assessment"]["minutes"], 75)

    def test_expert_content_runs_only_inside_the_attempt_and_its_score_is_kept(self):
        outside = self.invoke("submit_problem", {"problem_id": 9, "sourceCode": CODE})
        self.assertEqual(outside.status_code, 403)
        self.assertEqual(outside.json["error"]["code"], "assessment_only")
        self.invoke("start_assessment", {"technology_slug": "python"})
        inside = self.invoke("submit_problem", {"problem_id": 9, "sourceCode": CODE})
        self.assertEqual(inside.status_code, 201)
        self.assertEqual(self.repo.recorded, [(5, 2, 100)])
        # Running code is not a submission: nothing more is recorded.
        self.invoke("run_problem", {"problem_id": 9, "sourceCode": CODE})
        self.assertEqual(len(self.repo.recorded), 1)

    def test_the_tutor_is_off_during_an_attempt(self):
        self.invoke("start_assessment", {"technology_slug": "python"})
        submitted = self.invoke("submit_problem", {"problem_id": 9, "sourceCode": "print(0)"})
        tutor = self.invoke("tutor", {"problem_id": 9, "submissionId": submitted.json["submissionId"], "hintLevel": 2})
        self.assertEqual(tutor.status_code, 403)
        self.assertEqual(tutor.json["error"]["code"], "assessment_no_tutor")


if __name__ == "__main__":
    unittest.main()
