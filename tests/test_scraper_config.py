import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

import scraper


class RuntimeConfigTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_get_missing_env_vars_reports_required_runtime_config(self):
        missing = scraper.get_missing_env_vars()
        self.assertIn("DATABASE_URL", missing)
        self.assertIn("GEMINI_API_KEY", missing)
        self.assertIn("EMAIL_SENDER", missing)
        self.assertIn("EMAIL_PASSWORD", missing)

    @patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://example",
            "GEMINI_API_KEY": "test-key",
            "EMAIL_SENDER": "me@example.com",
            "EMAIL_PASSWORD": "app-pass",
        },
        clear=True,
    )
    def test_get_missing_env_vars_returns_empty_when_all_present(self):
        self.assertEqual(scraper.get_missing_env_vars(), [])

    @patch("scraper.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"cv-content")
    @patch("scraper.smtplib.SMTP_SSL")
    def test_send_email_normalizes_spaced_app_password(
        self, smtp_cls, _open_mock, _exists_mock
    ):
        smtp = MagicMock()
        smtp_cls.return_value.__enter__.return_value = smtp

        with patch("scraper.EMAIL_SENDER", "me@example.com"), patch(
            "scraper.EMAIL_PASSWORD", "abcd efgh ijkl mnop"
        ):
            scraper.send_application_email("to@example.com", "Role", "Company")

        smtp.login.assert_called_once_with("me@example.com", "abcdefghijklmnop")


if __name__ == "__main__":
    unittest.main()
