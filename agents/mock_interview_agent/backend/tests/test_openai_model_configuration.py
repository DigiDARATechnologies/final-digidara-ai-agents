"""Tests for fail-fast OpenAI configuration validation."""

import os
import unittest
from unittest.mock import patch

from ai import chat_client


class OpenAIModelConfigurationTests(unittest.TestCase):
    def test_current_default_models_validate(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            chat_client.validate_configured_models()

    def test_missing_api_key_fails_with_clear_startup_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                chat_client.validate_configured_models()

    def test_missing_chat_model_fails_with_clear_startup_error(self):
        with patch.object(chat_client, "MODEL", ""):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with self.assertRaisesRegex(RuntimeError, "OPENAI_MODEL"):
                    chat_client.validate_configured_models()


if __name__ == "__main__":
    unittest.main()
