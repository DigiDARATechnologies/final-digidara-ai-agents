import re
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).parents[2]
FRONTEND_SRC = PROJECT_DIR / "frontend" / "src"


class FrontendErrorHandlingContractTests(unittest.TestCase):
    def test_catch_handlers_are_not_empty_or_anonymous_silent_fallbacks(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in FRONTEND_SRC.rglob("*")
            if path.suffix in {".js", ".jsx"}
        )
        self.assertNotIn(".catch(() =>", sources)
        self.assertIsNone(re.search(r"\bcatch\s*\{", sources))
        self.assertIsNone(re.search(r"\bcatch\s*\([^)]*\)\s*\{\s*\}", sources))

    def test_client_logger_and_render_error_boundary_are_installed(self):
        logger_source = (
            FRONTEND_SRC / "utils" / "clientLogger.js"
        ).read_text(encoding="utf-8")
        main_source = (FRONTEND_SRC / "main.jsx").read_text(encoding="utf-8")
        boundary_source = (
            FRONTEND_SRC / "components" / "AppErrorBoundary.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn("JSON.stringify(payload)", logger_source)
        self.assertIn("<AppErrorBoundary>", main_source)
        self.assertIn("componentDidCatch", boundary_source)
        self.assertIn("reportClientError", boundary_source)

    def test_preflight_failures_have_user_visible_feedback(self):
        app_source = (FRONTEND_SRC / "App.jsx").read_text(encoding="utf-8")
        setup_source = (
            FRONTEND_SRC / "components" / "SetupScreen.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("startupWarning", app_source)
        self.assertIn('role="alert"', app_source)
        self.assertIn("quotaError", setup_source)
        self.assertIn('role="alert"', setup_source)


if __name__ == "__main__":
    unittest.main()
