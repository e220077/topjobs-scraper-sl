import unittest
from types import SimpleNamespace
from unittest.mock import patch

import scraper


class DummyAIResponse:
    def __init__(self, text):
        self.text = text


class AnalyzeJobWithGeminiTests(unittest.TestCase):
    def setUp(self):
        self.requests_patcher = patch(
            "scraper.requests.get", return_value=SimpleNamespace(content=b"fake-image")
        )
        self.image_open_patcher = patch("scraper.Image.open", return_value=object())
        self.requests_patcher.start()
        self.image_open_patcher.start()

    def tearDown(self):
        self.requests_patcher.stop()
        self.image_open_patcher.stop()

    def test_parses_string_skills_without_character_splitting(self):
        model_stub = SimpleNamespace(
            generate_content=lambda _payload: DummyAIResponse(
                '{"email":"dev@example.com","skills":"Java, Spring Boot"}'
            )
        )
        with patch("scraper.model", model_stub):
            email, skills = scraper.analyze_job_with_gemini(
                "https://example.com/job.png", "Java Engineer"
            )

        self.assertEqual(email, "dev@example.com")
        self.assertEqual(skills, "Java, Spring Boot")

    def test_falls_back_to_email_and_skills_when_json_is_missing(self):
        model_stub = SimpleNamespace(
            generate_content=lambda _payload: DummyAIResponse(
                "Please apply via hiring@example.com\nSkills: Java, AWS"
            )
        )
        with patch("scraper.model", model_stub):
            email, skills = scraper.analyze_job_with_gemini(
                "https://example.com/job.png", "Java Engineer"
            )

        self.assertEqual(email, "hiring@example.com")
        self.assertEqual(skills, "Java, AWS")


if __name__ == "__main__":
    unittest.main()
