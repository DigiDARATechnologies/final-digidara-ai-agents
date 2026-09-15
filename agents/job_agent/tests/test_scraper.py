import unittest

from job_agent.scraper import _parse_html_cards, _parse_json_ld
from job_agent.service import _clean_job


class ScraperParserTests(unittest.TestCase):
    def test_rejects_non_http_application_url(self):
        job = {
            "external_id": "unsafe-1",
            "title": "Developer",
            "company": "Example",
            "apply_url": "javascript:alert(1)",
        }
        self.assertIsNone(_clean_job(job))

    def test_json_ld_job_posting(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "identifier": {"value": "role-42"},
          "title": "Junior Python Developer",
          "hiringOrganization": {"name": "Example Pvt Ltd"},
          "jobLocation": {"address": {"addressLocality": "Chennai", "addressCountry": "IN"}},
          "description": "Build Flask APIs",
          "skills": "Python, Flask",
          "url": "/careers/role-42",
          "datePosted": "2026-09-01"
        }
        </script>
        """
        jobs = _parse_json_ld(html, "https://careers.example.com/jobs")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "role-42")
        self.assertEqual(jobs[0]["company"], "Example Pvt Ltd")
        self.assertEqual(jobs[0]["apply_url"], "https://careers.example.com/careers/role-42")

    def test_configured_html_cards(self):
        html = """
        <div class="job-card">
          <h2 class="title">Data Analyst</h2><span class="company">Example Data</span>
          <span class="place">Remote</span><a class="apply" href="/apply/7">Apply</a>
        </div>
        """
        config = {
            "item_selector": ".job-card",
            "fields": {
                "title": ".title",
                "company": ".company",
                "location": ".place",
                "apply_url": {"selector": "a.apply", "attribute": "href", "url": True},
            },
        }
        jobs = _parse_html_cards(html, "https://jobs.example.com/list", config)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["apply_url"], "https://jobs.example.com/apply/7")


if __name__ == "__main__":
    unittest.main()
