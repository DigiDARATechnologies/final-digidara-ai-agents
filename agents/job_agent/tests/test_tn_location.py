import unittest

from job_agent.tn_location import (
    ALL_TN_DISTRICTS,
    REGION_INTERNATIONAL,
    REGION_OTHER_INDIA,
    REGION_TAMIL_NADU,
    REGION_UNKNOWN,
    TYPE_HYBRID,
    TYPE_ONSITE,
    TYPE_REMOTE,
    TYPE_UNKNOWN,
    classify_district,
    classify_job_location,
    classify_location_type,
    classify_region,
)


class DistrictClassificationTests(unittest.TestCase):
    def test_major_tn_cities_resolve_to_their_district(self):
        self.assertEqual(classify_district("Chennai, Tamil Nadu, India"), "Chennai")
        self.assertEqual(classify_district("Coimbatore, India"), "Coimbatore")
        self.assertEqual(classify_district("Madurai"), "Madurai")
        self.assertEqual(classify_district("Salem, Tamil Nadu"), "Salem")

    def test_trichy_aliases_resolve_to_tiruchirappalli(self):
        self.assertEqual(classify_district("Trichy"), "Tiruchirappalli")
        self.assertEqual(classify_district("Tiruchirappalli, Tamil Nadu"), "Tiruchirappalli")

    def test_hosur_resolves_as_its_own_district(self):
        self.assertEqual(classify_district("Hosur, Tamil Nadu"), "Hosur")

    def test_all_32_tn_districts_are_present(self):
        self.assertEqual(len(ALL_TN_DISTRICTS), 32)
        for expected in (
            "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur",
            "Erode", "Vellore", "Tirunelveli", "Thoothukudi", "Thanjavur", "Dindigul",
            "Hosur", "Kanchipuram", "Chengalpattu", "Ranipet", "Krishnagiri", "Namakkal",
            "Karur", "Cuddalore", "Villupuram", "Kallakurichi", "Nagapattinam",
            "Mayiladuthurai", "Tenkasi", "Sivaganga", "Ramanathapuram", "Virudhunagar",
            "Pudukkottai", "Perambalur", "Ariyalur", "The Nilgiris",
        ):
            self.assertIn(expected, ALL_TN_DISTRICTS)

    def test_non_tn_locations_have_no_district(self):
        self.assertIsNone(classify_district("Bangalore, Karnataka"))
        self.assertIsNone(classify_district("Hyderabad, Telangana"))
        self.assertIsNone(classify_district("Remote"))
        self.assertIsNone(classify_district(""))
        self.assertIsNone(classify_district(None))


class RegionClassificationTests(unittest.TestCase):
    def test_tn_district_examples_from_spec(self):
        for location in ("Chennai", "Coimbatore, Tamil Nadu", "Hosur", "Salem", "Trichy"):
            district = classify_district(location)
            self.assertEqual(classify_region(location, district), REGION_TAMIL_NADU, location)

    def test_other_india_examples_from_spec(self):
        for location in ("Bangalore", "Hyderabad", "Pune"):
            district = classify_district(location)
            self.assertIsNone(district)
            self.assertEqual(classify_region(location, district), REGION_OTHER_INDIA, location)

    def test_bare_remote_is_unknown_region_not_tamil_nadu(self):
        # Section 10: do NOT automatically classify generic Remote as
        # Tamil Nadu, and don't invent OTHER_INDIA either without evidence.
        self.assertEqual(classify_region("Remote", None), REGION_UNKNOWN)

    def test_remote_with_a_tn_city_still_resolves_tamil_nadu(self):
        # "Remote - Chennai" (hybrid/remote-eligible but Chennai-based)
        # must still classify by the actual place named, not by "remote".
        location = "Remote - Chennai, India"
        district = classify_district(location)
        self.assertEqual(district, "Chennai")
        self.assertEqual(classify_region(location, district), REGION_TAMIL_NADU)

    def test_international_locations(self):
        for location in ("San Francisco, USA", "London, United Kingdom", "Toronto, Canada"):
            self.assertEqual(classify_region(location, None), REGION_INTERNATIONAL, location)

    def test_tamil_nadu_state_name_without_a_specific_district(self):
        self.assertEqual(classify_region("Tamil Nadu, India", None), REGION_TAMIL_NADU)

    def test_empty_location_is_unknown(self):
        self.assertEqual(classify_region("", None), REGION_UNKNOWN)
        self.assertEqual(classify_region(None, None), REGION_UNKNOWN)


class LocationTypeClassificationTests(unittest.TestCase):
    def test_remote_examples_from_spec(self):
        self.assertEqual(classify_location_type("Remote"), TYPE_REMOTE)

    def test_hybrid_is_detected(self):
        self.assertEqual(classify_location_type("Chennai (Hybrid)"), TYPE_HYBRID)

    def test_plain_place_name_defaults_to_onsite(self):
        self.assertEqual(classify_location_type("Chennai, Tamil Nadu, India"), TYPE_ONSITE)

    def test_empty_location_is_unknown_type(self):
        self.assertEqual(classify_location_type(""), TYPE_UNKNOWN)
        self.assertEqual(classify_location_type(None), TYPE_UNKNOWN)


class ClassifyJobLocationTests(unittest.TestCase):
    """The single entry point used by service._clean_job() for every job,
    regardless of which provider posted it."""

    def test_returns_district_region_and_type_together(self):
        district, region, location_type = classify_job_location("Coimbatore, Tamil Nadu, India")
        self.assertEqual(district, "Coimbatore")
        self.assertEqual(region, REGION_TAMIL_NADU)
        self.assertEqual(location_type, TYPE_ONSITE)

    def test_bangalore_job_from_a_tn_company_is_not_reclassified_as_tn(self):
        # The exact scenario section 9 warns about: a company known to be
        # in Tamil Nadu can still post a job located elsewhere, and that
        # job must NOT be counted as a Tamil Nadu job.
        district, region, location_type = classify_job_location("Bangalore, Karnataka")
        self.assertIsNone(district)
        self.assertEqual(region, REGION_OTHER_INDIA)
        self.assertEqual(location_type, TYPE_ONSITE)

    def test_remote_job(self):
        district, region, location_type = classify_job_location("Remote")
        self.assertIsNone(district)
        self.assertEqual(region, REGION_UNKNOWN)
        self.assertEqual(location_type, TYPE_REMOTE)


if __name__ == "__main__":
    unittest.main()
