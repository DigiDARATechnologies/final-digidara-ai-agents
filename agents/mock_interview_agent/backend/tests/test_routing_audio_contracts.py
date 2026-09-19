import ast
from io import BytesIO
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from flask import jsonify
from scoring import build_scorecard


BACKEND_DIR = Path(__file__).parents[1]
PROJECT_DIR = BACKEND_DIR.parent
APP_SOURCE = (BACKEND_DIR / "app.py").read_text(encoding="utf-8")
ANSWERS_SOURCE = (
    BACKEND_DIR / "routes" / "answers.py"
).read_text(encoding="utf-8")
FRONTEND_DIR = PROJECT_DIR / "frontend" / "src"
APP_JSX = (FRONTEND_DIR / "App.jsx").read_text(encoding="utf-8")
MAIN_JSX = (FRONTEND_DIR / "main.jsx").read_text(encoding="utf-8")
INTERVIEW_JSX = (
    FRONTEND_DIR / "components" / "InterviewScreen.jsx"
).read_text(encoding="utf-8")
SUBMISSION_HOOK = (
    FRONTEND_DIR / "hooks" / "useInterviewSubmission.js"
).read_text(encoding="utf-8")
SCORECARD_JSX = (
    FRONTEND_DIR / "components" / "QuestionScorecard.jsx"
).read_text(encoding="utf-8")


def answers_function_source(name):
    tree = ast.parse(ANSWERS_SOURCE)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(ANSWERS_SOURCE, node)


class RoutingContracts(unittest.TestCase):
    def test_bookmarkable_routes_are_declared(self):
        self.assertIn("<BrowserRouter>", MAIN_JSX)
        for path in (
            "/dashboard",
            "/new-interview",
            "/history",
            "/history/:interviewId",
            "/profile",
        ):
            self.assertIn(f'path="{path}"', APP_JSX)
        self.assertIn("useNavigate", APP_JSX)
        self.assertNotIn("const [screen, setScreen]", APP_JSX)


class AudioPersistenceContracts(unittest.TestCase):
    def test_transcription_saves_managed_audio_against_the_question(self):
        source = answers_function_source("transcribe")
        self.assertIn('request.form.get("question_order")', source)
        self.assertIn("AUDIO_UPLOAD_DIR", source)
        self.assertIn("SET answer_audio_path = %s", source)
        self.assertIn("BytesIO(audio_bytes)", source)

    def test_frontend_sends_question_identity_and_renders_audio(self):
        self.assertIn("questionOrder: submittedQuestion.order", SUBMISSION_HOOK)
        self.assertIn("<audio", SCORECARD_JSX)
        self.assertIn("item.answer_audio_path", SCORECARD_JSX)
        self.assertIn("item.followup.answer_audio_path", SCORECARD_JSX)

    def test_scorecard_preserves_main_and_followup_recording_paths(self):
        rows = [
            {
                "is_followup": False,
                "question": "Main?",
                "answer": "Main answer",
                "answer_audio_path": "/api/uploads/audio/main.webm",
                "verdict": "partial",
                "verdict_reason": "More detail needed.",
                "ideal_answer": "Main ideal",
            },
            {
                "is_followup": True,
                "question": "Follow-up?",
                "answer": "Follow-up answer",
                "answer_audio_path": "/api/uploads/audio/followup.webm",
                "verdict": "correct",
                "verdict_reason": "Clear.",
                "ideal_answer": "Follow-up ideal",
            },
        ]
        scorecard, _, _ = build_scorecard(rows)
        self.assertEqual(
            scorecard[0]["answer_audio_path"],
            "/api/uploads/audio/main.webm",
        )
        self.assertEqual(
            scorecard[0]["followup"]["answer_audio_path"],
            "/api/uploads/audio/followup.webm",
        )

    def test_transcription_endpoint_persists_recording_and_returns_path(self):
        fake_pil = types.ModuleType("PIL")
        fake_image = types.SimpleNamespace(
            DecompressionBombError=RuntimeError,
            Resampling=types.SimpleNamespace(LANCZOS=1),
        )
        fake_pil.Image = fake_image
        fake_pil.ImageOps = types.SimpleNamespace()
        fake_pil.UnidentifiedImageError = ValueError
        with patch.dict(sys.modules, {"PIL": fake_pil}):
            import app as app_module
            import routes.answers as answers_module

        detail = {
            "id": 81,
            "answer_audio_path": None,
            "round_type": "technical",
            "subject": "Python",
            "question": "What is a tuple in Python?",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_dir = Path(temporary_directory).resolve()
            with (
                patch.object(answers_module, "AUDIO_UPLOAD_DIR", upload_dir),
                patch.object(
                    answers_module.db,
                    "query",
                    side_effect=[(detail, None), (None, None)],
                ) as query,
                patch.object(
                    answers_module.groq_client,
                    "transcribe_audio",
                    return_value="Stored transcript",
                ) as transcribe_audio,
            ):
                response = app_module.app.test_client().post(
                    "/api/transcribe",
                    data={
                        "interview_id": "7",
                        "question_order": "2",
                        "audio": (
                            BytesIO(b"safe-test-recording"),
                            "answer.webm",
                            "audio/webm",
                        ),
                    },
                    content_type="multipart/form-data",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["transcript"], "Stored transcript")
            self.assertTrue(payload["audio_path"].startswith(
                "/api/uploads/audio/7-2-"
            ))
            saved_files = list(upload_dir.iterdir())
            self.assertEqual(len(saved_files), 1)
            self.assertEqual(saved_files[0].read_bytes(), b"safe-test-recording")
            self.assertIn("SET answer_audio_path = %s", query.call_args_list[1].args[0])
            transcribe_audio.assert_called_once_with(
                ANY,
                "answer.webm",
                "technical",
                subject="Python",
                question="What is a tuple in Python?",
            )


class BlueprintRegressionTests(unittest.TestCase):
    def test_evaluated_answer_retry_calls_usage_date_without_shadowing(self):
        fake_pil = types.ModuleType("PIL")
        fake_pil.Image = types.SimpleNamespace(
            DecompressionBombError=RuntimeError,
            Resampling=types.SimpleNamespace(LANCZOS=1),
        )
        fake_pil.ImageOps = types.SimpleNamespace()
        fake_pil.UnidentifiedImageError = ValueError
        with patch.dict(sys.modules, {"PIL": fake_pil}):
            import app as app_module
            import routes.answers as answers_module

        current = {
            "id": 11,
            "question_order": 1,
            "question": "What is a Python list?",
            "answer": "A mutable ordered collection.",
            "is_followup": False,
            "verdict": "correct",
            "verdict_reason": "The core concept is correct.",
            "ideal_answer": "A list is an ordered mutable collection.",
            "timed_out": False,
            "processing_status": "evaluated",
        }
        interview = {
            "id": 7,
            "student_id": 1,
            "status": "in_progress",
            "num_questions": 5,
            "difficulty": "beginner",
            "round_type": "technical",
            "subject": "python",
        }
        with app_module.app.test_request_context("/api/submit_answer"):
            with (
                patch.object(
                    answers_module.db,
                    "query",
                    side_effect=[
                        (current, None),
                        (interview, None),
                        (None, None),
                        ([current], None),
                    ],
                ),
                patch.object(
                    answers_module,
                    "get_usage_date",
                    return_value="2026-08-04",
                ) as get_usage_date,
                patch.object(
                    answers_module,
                    "daily_answered_count",
                    return_value=1,
                ),
                patch.object(
                    answers_module,
                    "_issue_next_question",
                    return_value=jsonify({"done": False}),
                ),
            ):
                response = answers_module._submit_answer({
                    "interview_id": 7,
                    "question_order": 1,
                    "answer": current["answer"],
                    "time_taken_sec": 12,
                    "timed_out": False,
                })

        self.assertEqual(response.status_code, 200)
        get_usage_date.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
