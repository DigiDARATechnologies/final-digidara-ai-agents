"""Certificate email: forgiving of common Gmail setup mistakes."""
import smtplib
import unittest
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from cert_app.services import exam_service


class SmtpSettingsTest(unittest.TestCase):
    def _settings(self, **values):
        defaults = dict(SMTP_HOST="smtp.gmail.com", SMTP_PORT=587, SMTP_USERNAME="certs@example.com",
                        SMTP_PASSWORD="abcd efgh ijkl mnop", SMTP_FROM=None, SMTP_USE_TLS=True)
        defaults.update(values)
        return patch.multiple(exam_service.settings, **defaults)

    def test_gmail_app_password_spaces_and_quotes_are_removed(self):
        with self._settings(SMTP_PASSWORD='"abcd efgh ijkl mnop"'):
            self.assertEqual(exam_service._smtp_password(), "abcdefghijklmnop")

    def test_other_providers_keep_the_password_as_is(self):
        with self._settings(SMTP_HOST="smtp.example.net", SMTP_PASSWORD="pass word"):
            self.assertEqual(exam_service._smtp_password(), "pass word")

    def test_smtp_user_is_accepted_when_smtp_username_is_missing(self):
        with self._settings(SMTP_USERNAME=None), patch.dict("os.environ", {"SMTP_USER": "ops@example.com"}):
            self.assertEqual(exam_service._smtp_username(), "ops@example.com")

    def test_login_uses_the_cleaned_password_over_starttls(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with self._settings(), patch.object(exam_service.smtplib, "SMTP", return_value=smtp):
            exam_service._send_smtp_message(EmailMessage())
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("certs@example.com", "abcdefghijklmnop")
        smtp.send_message.assert_called_once()

    def test_port_465_uses_a_direct_tls_connection(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with self._settings(SMTP_PORT=465), patch.object(exam_service.smtplib, "SMTP_SSL", return_value=smtp) as ssl_cls:
            exam_service._send_smtp_message(EmailMessage())
        ssl_cls.assert_called_once()
        smtp.starttls.assert_not_called()

    def test_a_rejected_login_gives_the_learner_a_friendly_error(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        with self._settings(), patch.object(exam_service.smtplib, "SMTP", return_value=smtp):
            with self.assertRaisesRegex(ValueError, "temporarily unavailable"):
                exam_service._send_smtp_message(EmailMessage())


if __name__ == "__main__":
    unittest.main()
