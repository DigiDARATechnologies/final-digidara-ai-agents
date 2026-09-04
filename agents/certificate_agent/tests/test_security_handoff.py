import unittest
from fastapi.testclient import TestClient

from cert_app.main import app
from cert_app.services.auth_service import create_access_token
from cert_app.db.database import init_db


class TestSecurityAndHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.valid_token = create_access_token({
            "sub": "123",
            "name": "Security Tester",
            "email": "security@example.com"
        })

    def test_debug_auth_endpoint_removed(self):
        """GET /debug-auth must return 404 Not Found."""
        res = self.client.get("/debug-auth")
        self.assertEqual(res.status_code, 404)

    def test_home_route_invalid_jwt_falls_back_to_login(self):
        """GET / with an invalid/unverified JWT query param must serve index.html."""
        res = self.client.get("/?token=invalid_forged_jwt_12345")
        self.assertEqual(res.status_code, 200)
        # Should serve index.html (contains loginPanel)
        self.assertIn("loginPanel", res.text)
        self.assertNotIn("id=\"questionContainer\"", res.text)

    def test_home_route_valid_jwt_bypasses_login(self):
        """GET / with a cryptographically valid JWT serves exam.html."""
        res = self.client.get(f"/?token={self.valid_token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("question-card", res.text)

    def test_handoff_and_exchange_flow(self):
        """Test single-use handoff code generation and exchange."""
        # 1. Handoff request with invalid token fails
        res_bad = self.client.post("/api/auth/handoff", json={"token": "bad_token"})
        self.assertEqual(res_bad.status_code, 401)

        # 2. Handoff request with valid token succeeds
        res_good = self.client.post(
            "/api/auth/handoff",
            json={"token": self.valid_token, "topic": "Python Security"}
        )
        self.assertEqual(res_good.status_code, 200)
        data = res_good.json()
        self.assertIn("code", data)
        code = data["code"]

        # 3. GET /?code=<valid_code> serves exam.html
        res_home = self.client.get(f"/?code={code}")
        self.assertEqual(res_home.status_code, 200)
        self.assertIn("question-card", res_home.text)

        # 4. Exchange code for session token
        res_ex = self.client.post("/api/auth/exchange", json={"code": code})
        self.assertEqual(res_ex.status_code, 200)
        ex_data = res_ex.json()
        self.assertEqual(ex_data["access_token"], self.valid_token)
        self.assertEqual(ex_data["topic"], "Python Security")

        # 5. Second exchange of the SAME code must fail (single-use)
        res_ex2 = self.client.post("/api/auth/exchange", json={"code": code})
        self.assertEqual(res_ex2.status_code, 400)

    def test_handoff_topic_url_encoding(self):
        """Topic with special characters must be URL-encoded in exchange_url."""
        res = self.client.post(
            "/api/auth/handoff",
            json={"token": self.valid_token, "topic": "Python & Data Science #1"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("topic=Python%20%26%20Data%20Science%20%231", data["exchange_url"])

    def test_spoofed_x_forwarded_for_ignored_when_proxy_trust_disabled(self):
        """With TRUST_PROXY_HEADERS=False, spoofed X-Forwarded-For headers are ignored and connection IP rate limits apply."""
        from unittest.mock import patch, MagicMock
        from cert_app.api.auth import exchange_rate_limiter

        # Reset rate limiter state for testclient IP
        with exchange_rate_limiter.lock:
            exchange_rate_limiter.ip_requests.clear()

        mock_settings = MagicMock()
        mock_settings.TRUST_PROXY_HEADERS = False

        with patch("cert_app.api.auth.get_settings", return_value=mock_settings):
            # Send 10 exchange requests with spoofed distinct X-Forwarded-For headers
            for i in range(10):
                res = self.client.post(
                    "/api/auth/exchange",
                    json={"code": f"invalid_code_{i}"},
                    headers={"X-Forwarded-For": f"192.168.1.{i+1}"}
                )
                self.assertEqual(res.status_code, 400)  # Invalid code, but passed rate limit check

            # 11th request from same connection must hit rate limit (429), despite spoofed header
            res_rate_limited = self.client.post(
                "/api/auth/exchange",
                json={"code": "invalid_code_11"},
                headers={"X-Forwarded-For": "192.168.1.99"}
            )
            self.assertEqual(res_rate_limited.status_code, 429)
            self.assertIn("Too many authentication exchange attempts", res_rate_limited.json()["detail"])

    def test_api_endpoints_still_require_authorization(self):
        """Protected API endpoints must reject requests without valid Bearer token."""
        # /api/auth/me
        res_me = self.client.get("/api/auth/me")
        self.assertIn(res_me.status_code, [401, 403])

        # /api/exam/start
        res_exam = self.client.post("/api/exam/start", json={"topic": "Python"})
        self.assertIn(res_exam.status_code, [401, 403])

        # /api/chat/start
        res_chat = self.client.post("/api/chat/start", json={"topic": "Python"})
        self.assertIn(res_chat.status_code, [401, 403])


if __name__ == "__main__":
    unittest.main()
