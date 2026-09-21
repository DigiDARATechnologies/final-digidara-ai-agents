"""Platform account export/erasure reaching Mock Interview through /api/invoke."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-unused")

import db  # noqa: E402
import privacy  # noqa: E402
from app import app  # noqa: E402

HEADERS = {"X-DigiDARA-User-ID": "platform-user-1"}


class PrivacyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def invoke(self, action, email="a@b.com", headers=HEADERS):
        return self.client.post("/api/invoke", json={"action": action, "payload": {"email": email}}, headers=headers)

    def test_requires_verified_identity(self):
        self.assertEqual(self.invoke("export_user_data", headers={}).status_code, 401)
        self.assertEqual(self.invoke("delete_user_data", headers={}).status_code, 401)

    def test_requires_a_valid_email(self):
        self.assertEqual(self.invoke("export_user_data", email="nope").status_code, 400)

    def test_unknown_learner_has_nothing_to_export_or_erase(self):
        with patch.object(db, "query", return_value=(None, None)):
            self.assertEqual(self.invoke("export_user_data").get_json(), {"profile": None})
            self.assertEqual(self.invoke("delete_user_data").get_json(), {"status": "no_data"})

    def test_erase_wipes_personal_fields_recordings_and_history(self):
        calls = []

        def fake_query(sql, params=None, fetch=False, fetchone=False):
            calls.append((" ".join(sql.split()), params))
            if sql.startswith("SELECT * FROM students"):
                return {"id": 7, "avatar_url": "/uploads/avatars/a.png"}, None
            if "answer_audio_path FROM" in sql:
                return [{"answer_audio_path": "/uploads/audio/x.webm"}], None
            return None, None

        removed = []
        with patch.object(db, "query", side_effect=fake_query), \
                patch.object(privacy, "delete_managed_audio", removed.append), \
                patch.object(privacy, "delete_managed_avatar", removed.append):
            body = self.invoke("delete_user_data").get_json()

        self.assertEqual(body, {"status": "erased", "id": 7})
        self.assertEqual(removed, ["/uploads/audio/x.webm", "/uploads/avatars/a.png"])
        statements = " | ".join(sql for sql, _ in calls)
        self.assertIn("SET d.answer = NULL", statements)
        self.assertIn("DELETE FROM user_question_history", statements)
        update = next(item for item in calls if item[0].startswith("UPDATE students"))
        self.assertEqual(update[1], ("erased-7@erased.invalid", 7))


if __name__ == "__main__":
    unittest.main()
