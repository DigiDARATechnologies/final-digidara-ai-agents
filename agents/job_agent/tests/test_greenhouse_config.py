import os
import tempfile
import unittest

from job_agent.providers.config_loader import get_apify_config, get_greenhouse_companies, load_providers_config


class GreenhouseConfigTests(unittest.TestCase):
    def test_enabled_configuration_loads_companies(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [
                    {"name": "Sagent India", "board_id": "sagentindia", "enabled": True},
                    {"name": "Appian", "board_id": "appian", "enabled": True},
                ],
            }
        }
        companies = get_greenhouse_companies(config)
        self.assertEqual(len(companies), 2)
        # Registry entries also carry informational metadata fields
        # (district/city/state/country/category) - None here since the
        # test config didn't set any - so check name/board_id rather than
        # exact dict equality.
        self.assertEqual(companies[0]["name"], "Sagent India")
        self.assertEqual(companies[0]["board_id"], "sagentindia")
        self.assertEqual(companies[1]["name"], "Appian")
        self.assertEqual(companies[1]["board_id"], "appian")

    def test_provider_disabled_returns_no_companies(self):
        config = {
            "greenhouse": {
                "enabled": False,
                "companies": [{"name": "Sagent India", "board_id": "sagentindia", "enabled": True}],
            }
        }
        self.assertEqual(get_greenhouse_companies(config), [])

    def test_disabled_company_is_skipped(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [
                    {"name": "Sagent India", "board_id": "sagentindia", "enabled": True},
                    {"name": "Zenoti", "board_id": "zenoti", "enabled": False},
                ],
            }
        }
        companies = get_greenhouse_companies(config)
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["board_id"], "sagentindia")

    def test_missing_board_id_is_skipped(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [
                    {"name": "No Board Id Co", "enabled": True},
                    {"name": "Appian", "board_id": "appian", "enabled": True},
                ],
            }
        }
        companies = get_greenhouse_companies(config)
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["name"], "Appian")

    def test_missing_name_is_skipped(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [{"board_id": "sagentindia", "enabled": True}],
            }
        }
        self.assertEqual(get_greenhouse_companies(config), [])

    def test_company_enabled_defaults_true_when_omitted(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [{"name": "Sagent India", "board_id": "sagentindia"}],
            }
        }
        companies = get_greenhouse_companies(config)
        self.assertEqual(len(companies), 1)

    def test_duplicate_board_id_only_counted_once(self):
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": [
                    {"name": "Sagent India", "board_id": "sagentindia", "enabled": True},
                    {"name": "Sagent India Duplicate", "board_id": "sagentindia", "enabled": True},
                ],
            }
        }
        companies = get_greenhouse_companies(config)
        self.assertEqual(len(companies), 1)

    def test_load_providers_config_from_real_yaml_file(self):
        yaml_content = """
greenhouse:
  enabled: true
  companies:
    - name: Sagent India
      board_id: sagentindia
      enabled: true
    - name: Appian
      board_id: appian
      enabled: true
apify:
  enabled: false
  actors: []
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
            handle.write(yaml_content)
            path = handle.name
        try:
            config = load_providers_config(path)
            companies = get_greenhouse_companies(config)
            self.assertEqual(len(companies), 2)
            apify = get_apify_config(config)
            self.assertFalse(apify["enabled"])
        finally:
            os.unlink(path)

    def test_missing_config_file_returns_empty_mapping(self):
        config = load_providers_config("/nonexistent/path/providers.yaml")
        self.assertEqual(config, {})
        self.assertEqual(get_greenhouse_companies(config), [])

    def test_seed_providers_yaml_ships_with_configured_companies(self):
        from job_agent.providers.config_loader import DEFAULT_CONFIG_PATH

        config = load_providers_config(DEFAULT_CONFIG_PATH)
        companies = get_greenhouse_companies(config)
        board_ids = {company["board_id"] for company in companies}
        # Core companies must always be present; the full list grows over
        # time, though individual companies do get `enabled: false` when
        # their Greenhouse board is confirmed gone (see providers.yaml
        # comments) - so this checks "still many companies", not an exact
        # count. Zenoti and several others from an earlier, less-verified
        # registry are gone: this milestone replaced the source list with
        # a smaller, verified Tamil Nadu technology set (see
        # providers/README.md).
        self.assertTrue({"sagentindia", "appian", "appviewx"}.issubset(board_ids))
        self.assertGreaterEqual(len(companies), 15)

    def test_seed_providers_yaml_companies_carry_tn_registry_metadata(self):
        from job_agent.providers.config_loader import DEFAULT_CONFIG_PATH

        config = load_providers_config(DEFAULT_CONFIG_PATH)
        companies = {c["board_id"]: c for c in get_greenhouse_companies(config)}
        appviewx = companies["appviewx"]
        self.assertEqual(appviewx["district"], "Coimbatore")
        self.assertEqual(appviewx["state"], "Tamil Nadu")
        self.assertTrue(appviewx["category"])

    def test_seed_providers_yaml_verified_dead_boards_are_disabled_not_removed(self):
        from job_agent.providers.config_loader import DEFAULT_CONFIG_PATH

        config = load_providers_config(DEFAULT_CONFIG_PATH)
        enabled_ids = {c["board_id"] for c in get_greenhouse_companies(config)}
        # Confirmed offline 2026-09-03 (both API and hosted page checked
        # live) - kept in the file for history/re-enabling, but excluded
        # from the active registry.
        for dead_board_id in ("tekion", "integrate", "arcadiacareers", "pleo", "perchenergycareers"):
            self.assertNotIn(dead_board_id, enabled_ids)

    def test_seed_providers_yaml_pending_validation_candidates_are_excluded(self):
        from job_agent.providers.config_loader import (
            DEFAULT_CONFIG_PATH,
            get_pending_validation_companies,
        )

        config = load_providers_config(DEFAULT_CONFIG_PATH)
        enabled_ids = {c["board_id"] for c in get_greenhouse_companies(config)}
        self.assertNotIn("karat", enabled_ids)

        pending = {c["name"] for c in get_pending_validation_companies(config)}
        self.assertIn("Karat", pending)

    def test_seed_providers_yaml_ships_with_target_location_filters(self):
        from job_agent.providers.config_loader import DEFAULT_CONFIG_PATH, get_greenhouse_filters

        config = load_providers_config(DEFAULT_CONFIG_PATH)
        filters = get_greenhouse_filters(config)
        self.assertTrue(filters["entry_level_only"])
        for keyword in ("chennai", "bengaluru", "hyderabad"):
            self.assertIn(keyword, filters["location_keywords"])


if __name__ == "__main__":
    unittest.main()
