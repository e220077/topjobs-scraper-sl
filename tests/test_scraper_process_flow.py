import re
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import scraper


def build_row(title, company):
    html = f"""
    <tr id="tr1" onclick="createAlert('1','2','3','4','5')">
      <td></td><td></td>
      <td><h2>{title}</h2><h1>{company}</h1></td>
    </tr>
    """
    return BeautifulSoup(html, "html.parser").find("tr")


class ProcessFlowTests(unittest.TestCase):
    def setUp(self):
        self.pattern = re.compile(
            r"createAlert\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\)"
        )

    def test_skips_ai_when_page_email_exists_and_title_already_matches(self):
        row = build_row("Senior Java Engineer", "Example Co")
        with patch(
            "scraper.get_vacancy_page_details",
            return_value=(
                "https://example.com/img.jpg",
                "jobs@example.com",
                "Senior Java Engineer Spring Boot AWS",
            ),
        ), patch("scraper.analyze_job_with_gemini") as analyze_mock, patch(
            "scraper.save_job"
        ) as save_mock:
            result = scraper.process_single_job(row, self.pattern)

        self.assertTrue(result)
        analyze_mock.assert_not_called()
        save_mock.assert_called_once()

    def test_uses_ai_when_page_email_missing_and_no_title_match(self):
        row = build_row("Senior Software Engineer", "Example Co")
        with patch(
            "scraper.get_vacancy_page_details",
            return_value=("https://example.com/img.jpg", None, ""),
        ), patch(
            "scraper.analyze_job_with_gemini", return_value=("jobs@example.com", "Python, AWS")
        ) as analyze_mock, patch("scraper.save_job") as save_mock:
            result = scraper.process_single_job(row, self.pattern)

        self.assertTrue(result)
        analyze_mock.assert_called_once()
        save_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
