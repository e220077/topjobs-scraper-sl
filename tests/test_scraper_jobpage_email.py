import unittest

import scraper


class JobPageEmailExtractionTests(unittest.TestCase):
    def test_extract_contact_email_prefers_non_topjobs_address(self):
        html = """
        <html>
          <body>
            Contact us at support@topjobs.lk
            Apply to careers@akbar.com
          </body>
        </html>
        """
        self.assertEqual(scraper.extract_contact_email(html), "careers@akbar.com")

    def test_extract_contact_email_returns_none_when_only_topjobs_email_exists(self):
        html = "<html><body>For issues: support@topjobs.lk</body></html>"
        self.assertIsNone(scraper.extract_contact_email(html))

    def test_normalize_job_link_rewrites_applicant_servlet_url(self):
        original = "https://www.topjobs.lk/applicant/JobAdvertismentServlet?rid=1&ac=2"
        expected = "https://www.topjobs.lk/employer/?rid=1&ac=2"
        self.assertEqual(scraper.normalize_job_link(original), expected)


if __name__ == "__main__":
    unittest.main()
