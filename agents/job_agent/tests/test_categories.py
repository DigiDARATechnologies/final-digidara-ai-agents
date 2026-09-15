import unittest

from job_agent.categories import (
    DEFAULT_CATEGORIES,
    OTHER_CATEGORY,
    categorize_course_name,
    categorize_job,
    categorize_text,
    category_labels,
    load_categories,
    related_category_ids,
)


class CategorizeTextTests(unittest.TestCase):
    def test_gen_ai_takes_priority_over_generic_ai_ml(self):
        self.assertEqual(categorize_text("Generative AI Engineer"), "gen_ai_agentic_ai")
        self.assertEqual(categorize_text("Agentic AI Developer"), "gen_ai_agentic_ai")
        self.assertEqual(categorize_text("LangChain Developer"), "gen_ai_agentic_ai")

    def test_ai_ml_matches_when_not_gen_ai_specific(self):
        self.assertEqual(categorize_text("Machine Learning Engineer"), "ai_ml")
        self.assertEqual(categorize_text("Deep Learning Researcher"), "ai_ml")

    def test_data_science_vs_data_analytics(self):
        self.assertEqual(categorize_text("Data Scientist"), "data_science")
        self.assertEqual(categorize_text("Data Analyst"), "data_analytics")
        self.assertEqual(categorize_text("BI Analyst"), "data_analytics")

    def test_python_full_stack(self):
        self.assertEqual(categorize_text("Python Full Stack Developer"), "python_full_stack")
        self.assertEqual(categorize_text("Backend Engineer (Django)"), "python_full_stack")

    def test_digital_marketing(self):
        self.assertEqual(categorize_text("Digital Marketing Specialist"), "digital_marketing")
        self.assertEqual(categorize_text("SEO Analyst"), "digital_marketing")

    def test_unrelated_titles_fall_back_to_other(self):
        self.assertEqual(categorize_text("Human Resources Operations Specialist"), OTHER_CATEGORY)
        self.assertEqual(categorize_text("Compensation Analyst III"), OTHER_CATEGORY)
        self.assertEqual(categorize_text(""), OTHER_CATEGORY)

    def test_bare_analyst_does_not_false_positive_into_data_analytics(self):
        # "Compensation Analyst" must not match just because it contains "analyst" -
        # only specific multi-word phrases like "data analyst" should match.
        self.assertEqual(categorize_text("Compensation Analyst"), OTHER_CATEGORY)
        self.assertEqual(categorize_text("Salesforce Analyst"), OTHER_CATEGORY)


class CategorizeJobTests(unittest.TestCase):
    def test_title_and_department_are_checked(self):
        self.assertEqual(categorize_job("Software Engineer", department="Engineering - Python Full Stack"), "python_full_stack")

    def test_description_is_never_used_for_classification(self):
        # Regression test: description text used to be a fallback signal,
        # but real collected jobs showed it's mostly unrelated company
        # boilerplate - e.g. every posting at an "agentic AI" company
        # mentions "AI agents" in its intro regardless of the actual role,
        # which miscategorized that company's Process Specialist and
        # Project Coordinator postings as Gen AI & Agentic AI, and a
        # generic "we value our people" blurb miscategorized IT Admin and
        # HR postings as Digital Marketing. Title/department must decide
        # this alone now.
        job_category = categorize_job(
            "Associate Engineer", department="Engineering",
            description="You will build generative AI agents using LangChain and LLMs.",
        )
        self.assertEqual(job_category, OTHER_CATEGORY)

    def test_real_world_boilerplate_no_longer_misclassifies_unrelated_roles(self):
        # The exact real-world cases that motivated this fix.
        self.assertEqual(
            categorize_job("Job ID 199 - Process Specialist", department="Business Operations",
                            description="...our agentic marketing platform... AI agents work together..."),
            OTHER_CATEGORY,
        )
        self.assertEqual(
            categorize_job("IT Admin", department="People",
                            description="We believe in a marketing-led, people-first culture..."),
            OTHER_CATEGORY,
        )

    def test_no_match_anywhere_returns_other(self):
        self.assertEqual(
            categorize_job("Office Administrator", department="Facilities", description="General office duties."),
            OTHER_CATEGORY,
        )


class CategorizeCourseNameTests(unittest.TestCase):
    """Course names are short, curated admin text ("Python", "AI/ML"), unlike
    noisy scraped job titles, so they need their own, more lenient matching."""

    def test_bare_course_names_matching_real_stored_data(self):
        # These are real course_name values seen in cert_students during
        # manual verification - a bare "Python" must resolve correctly.
        self.assertEqual(categorize_course_name("Python"), "python_full_stack")
        self.assertEqual(categorize_course_name("Machine learning"), "ai_ml")

    def test_course_catalog_names(self):
        self.assertEqual(categorize_course_name("AI/ML"), "ai_ml")
        self.assertEqual(categorize_course_name("Gen AI and Agentic AI"), "gen_ai_agentic_ai")
        self.assertEqual(categorize_course_name("Python Full Stack"), "python_full_stack")
        self.assertEqual(categorize_course_name("Data Science"), "data_science")
        self.assertEqual(categorize_course_name("Data Analytics"), "data_analytics")
        self.assertEqual(categorize_course_name("Digital Marketing"), "digital_marketing")

    def test_job_only_keywords_do_not_leak_into_course_matching_incorrectly(self):
        # "python developer" (a job keyword) still contains "python", so this
        # should still resolve via course_keywords, not fail - sanity check
        # that course matching isn't accidentally stricter than job matching.
        self.assertEqual(categorize_course_name("Python Developer Track"), "python_full_stack")

    def test_unrelated_or_empty_course_name_falls_back_to_other(self):
        self.assertEqual(categorize_course_name("Cloud Computing"), OTHER_CATEGORY)
        self.assertEqual(categorize_course_name(""), OTHER_CATEGORY)
        self.assertEqual(categorize_course_name(None), OTHER_CATEGORY)

    def test_falls_back_to_keywords_when_course_keywords_not_configured(self):
        custom = [{"id": "custom_track", "label": "Custom Track", "keywords": ["custom keyword"]}]
        self.assertEqual(categorize_course_name("a custom keyword here", custom), "custom_track")


class RelatedCategoryTests(unittest.TestCase):
    """Python is foundational for Data Analytics/Data Science/AI-ML/Gen AI,
    so a Python-track student should see those too ("broader relevant
    jobs"), but Digital Marketing shares no technical skill base and must
    stay isolated so it never bleeds into those results."""

    def test_python_full_stack_is_related_to_the_data_and_ai_cluster(self):
        related = related_category_ids("python_full_stack")
        self.assertEqual(related, {"data_analytics", "data_science", "ai_ml", "gen_ai_agentic_ai"})

    def test_digital_marketing_has_no_related_categories(self):
        self.assertEqual(related_category_ids("digital_marketing"), set())

    def test_related_categories_never_include_digital_marketing(self):
        for category_id in ("python_full_stack", "data_science", "data_analytics", "ai_ml", "gen_ai_agentic_ai"):
            self.assertNotIn("digital_marketing", related_category_ids(category_id))

    def test_a_category_is_never_related_to_itself(self):
        for category_id in ("python_full_stack", "data_science", "data_analytics", "ai_ml", "gen_ai_agentic_ai", "digital_marketing"):
            self.assertNotIn(category_id, related_category_ids(category_id))

    def test_unknown_category_returns_empty_set(self):
        self.assertEqual(related_category_ids("not_a_real_category"), set())

    def test_unknown_related_id_in_custom_config_is_dropped(self):
        # load_categories() only cleans related_categories when loading from
        # a real YAML file (that's where untrusted/typo'd config arrives),
        # so exercise it through a temp file rather than the raw list.
        import os
        import tempfile

        import yaml as yaml_module

        custom = [
            {"id": "a", "label": "A", "keywords": ["a"], "related_categories": ["b", "does_not_exist", "a"]},
            {"id": "b", "label": "B", "keywords": ["b"]},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
            yaml_module.safe_dump({"categories": custom}, handle)
            path = handle.name
        try:
            categories = load_categories(path)
            entry_a = next(c for c in categories if c["id"] == "a")
            # "does_not_exist" and the self-reference "a" are dropped, "b" kept.
            self.assertEqual(entry_a["related_categories"], ["b"])
        finally:
            os.unlink(path)


class CategoryConfigTests(unittest.TestCase):
    def test_default_categories_all_have_required_fields(self):
        for category in DEFAULT_CATEGORIES:
            self.assertIn("id", category)
            self.assertIn("label", category)
            self.assertTrue(category["keywords"])
            self.assertTrue(category["course_keywords"])
            self.assertIn("related_categories", category)

    def test_loaded_categories_always_have_course_keywords(self):
        for category in load_categories():
            self.assertIn("course_keywords", category)
            self.assertTrue(category["course_keywords"])

    def test_missing_config_file_falls_back_to_defaults(self):
        categories = load_categories("/nonexistent/categories.yaml")
        self.assertEqual([c["id"] for c in categories], [c["id"] for c in DEFAULT_CATEGORIES])

    def test_category_labels_include_other(self):
        labels = category_labels()
        self.assertEqual(labels[OTHER_CATEGORY], "Other")
        self.assertIn("python_full_stack", labels)

    def test_custom_config_overrides_defaults(self):
        custom = [{"id": "custom_track", "label": "Custom Track", "keywords": ["custom keyword"]}]
        self.assertEqual(categorize_text("this has a custom keyword in it", custom), "custom_track")
        self.assertEqual(categorize_text("nothing relevant here", custom), OTHER_CATEGORY)


if __name__ == "__main__":
    unittest.main()
