import os
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
