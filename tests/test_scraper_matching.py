import unittest

import scraper


class MatchingHeuristicsTests(unittest.TestCase):
    def test_extract_target_skills_does_not_treat_javascript_as_java(self):
        skills = scraper.extract_target_skills(
            "Frontend Developer (JavaScript/TypeScript, React)"
        )
        self.assertNotIn("Java", skills)

    def test_extract_target_skills_matches_java_roles(self):
        skills = scraper.extract_target_skills(
            "Senior Java Software Engineer - Spring Boot, AWS"
        )
        self.assertIn("Java", skills)
        self.assertIn("Spring Boot", skills)
        self.assertIn("AWS", skills)

    def test_extract_target_skills_matches_software_engineer_role(self):
        skills = scraper.extract_target_skills("Senior Software Engineer")
        self.assertIn("Software Engineer", skills)

    def test_should_use_ai_fallback_is_false_when_page_has_skills_and_email(self):
        self.assertFalse(
            scraper.should_use_ai_fallback(
                job_title="Senior Java Engineer",
                page_skills=["Java", "Spring Boot"],
                page_email="jobs@example.com",
            )
        )

    def test_should_use_ai_fallback_is_true_when_page_data_is_insufficient(self):
        self.assertTrue(
            scraper.should_use_ai_fallback(
                job_title="Senior Software Engineer",
                page_skills=[],
                page_email=None,
            )
        )


if __name__ == "__main__":
    unittest.main()
