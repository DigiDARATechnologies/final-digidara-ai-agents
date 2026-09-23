import ast
import sqlite3
import unittest
from pathlib import Path

from pagination import pagination_metadata


BACKEND_DIR = Path(__file__).parents[1]
PROJECT_DIR = BACKEND_DIR.parent
APP_SOURCE = (BACKEND_DIR / "app.py").read_text(encoding="utf-8")
ANSWERS_SOURCE = (
    BACKEND_DIR / "routes" / "answers.py"
).read_text(encoding="utf-8")
DASHBOARD_SOURCE = (
    BACKEND_DIR / "routes" / "dashboard.py"
).read_text(encoding="utf-8")
HISTORY_ROUTE_SOURCE = (
    BACKEND_DIR / "routes" / "history.py"
).read_text(encoding="utf-8")
INTERVIEWS_SOURCE = (
    BACKEND_DIR / "routes" / "interviews.py"
).read_text(encoding="utf-8")
HISTORY_SOURCE = (
    PROJECT_DIR / "frontend" / "src" / "components" / "History.jsx"
).read_text(encoding="utf-8")
API_SOURCE = (PROJECT_DIR / "frontend" / "src" / "api.js").read_text(
    encoding="utf-8"
)


def function_source(module_source, name):
    tree = ast.parse(module_source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(module_source, node)


class PaginationTests(unittest.TestCase):
    def test_metadata_identifies_first_middle_and_final_pages(self):
        self.assertEqual(
            pagination_metadata(23, 1, 10),
            {
                "page": 1,
                "limit": 10,
                "total_items": 23,
                "total_pages": 3,
                "has_more": True,
            },
        )
        self.assertTrue(pagination_metadata(23, 2, 10)["has_more"])
        self.assertFalse(pagination_metadata(23, 3, 10)["has_more"])
        self.assertEqual(pagination_metadata(0, 1, 10)["total_pages"], 0)

    def test_history_uses_two_fixed_queries_and_one_grouped_detail_count(self):
        source = function_source(HISTORY_ROUTE_SOURCE, "history")
        self.assertEqual(source.count("db.query("), 2)
        self.assertIn("WITH paged_interviews AS", source)
        self.assertIn("FROM interview_details d", source)
        self.assertIn("LEFT JOIN detail_totals d", source)
        self.assertIn("COUNT(d.id) AS total_questions", source)
        self.assertNotIn("(SELECT COUNT(*)", source)
        self.assertIn('"items": interviews', source)
        self.assertIn('"pagination": pagination_metadata', source)

    def test_frontend_requests_pages_and_exposes_load_more(self):
        self.assertIn("page: String(page)", API_SOURCE)
        self.assertIn("limit: String(limit)", API_SOURCE)
        self.assertIn("Load more interviews", HISTORY_SOURCE)
        self.assertIn("response.pagination", HISTORY_SOURCE)

    def test_grouped_detail_counts_match_the_legacy_correlated_counts(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE interviews (id INTEGER PRIMARY KEY);
            CREATE TABLE interview_details (
              id INTEGER PRIMARY KEY,
              interview_id INTEGER NOT NULL
            );
            INSERT INTO interviews (id) VALUES (1), (2), (3);
            INSERT INTO interview_details (id, interview_id)
            VALUES (1, 1), (2, 1), (3, 3), (4, 3), (5, 3);
            """
        )
        legacy = connection.execute(
            """SELECT i.id,
                      (SELECT COUNT(*) FROM interview_details d
                       WHERE d.interview_id = i.id) AS detail_count
                 FROM interviews i ORDER BY i.id"""
        ).fetchall()
        grouped = connection.execute(
            """SELECT i.id, COUNT(d.id) AS detail_count
                 FROM interviews i
                 LEFT JOIN interview_details d ON d.interview_id = i.id
                GROUP BY i.id ORDER BY i.id"""
        ).fetchall()
        connection.close()
        self.assertEqual(grouped, legacy)


class DashboardQueryTests(unittest.TestCase):
    def test_dashboard_uses_three_queries_and_bounded_history_rows(self):
        source = function_source(DASHBOARD_SOURCE, "dashboard")
        self.assertEqual(source.count("db.query("), 3)
        self.assertIn("LIMIT 10", source)
        self.assertIn("subject_averages AS", source)
        self.assertNotRegex(source, r"\bLIMIT\s+1\b")

    def test_dashboard_uses_cache_and_completion_invalidates_it(self):
        dashboard_source = function_source(DASHBOARD_SOURCE, "dashboard")
        completion_source = function_source(INTERVIEWS_SOURCE, "end_interview")
        self.assertIn("dashboard_cache.get_with_generation", dashboard_source)
        self.assertIn("dashboard_cache.set_if_generation", dashboard_source)
        self.assertIn("dashboard_cache.invalidate", completion_source)
        self.assertGreater(
            completion_source.index("dashboard_cache.invalidate"),
            completion_source.index("UPDATE interviews SET"),
        )


class BatchEvaluationContractTests(unittest.TestCase):
    def test_submit_path_never_generates_a_followup(self):
        source = function_source(ANSWERS_SOURCE, "_submit_answer")
        self.assertIn("batch_answer_saved = True", source)
        self.assertNotIn("generate_followup", source)
        self.assertNotIn("should_generate_followup", source)
        self.assertNotIn("is_followup: True", source)


if __name__ == "__main__":
    unittest.main()
