import unittest

from pipeline.demographic_correlation import (
    DEMOGRAPHICS,
    OUTCOMES,
    PARTY_SWINGS,
    build_dataset,
    build_web_payload,
    compute_correlations,
    load_regions,
    normalize_province,
)


class TestDemographicCorrelation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = build_dataset()

    def test_province_join_is_complete(self):
        self.assertEqual(len(self.frame), 81)
        self.assertEqual(self.frame["key"].nunique(), 81)
        self.assertFalse(self.frame[DEMOGRAPHICS + OUTCOMES + ["region"]].isna().any().any())

    def test_party_swings_are_present(self):
        for party in PARTY_SWINGS:
            self.assertIn(f"{party}_swing", self.frame)
            self.assertTrue(self.frame[f"{party}_swing"].notna().all())

    def test_regions_cover_all_provinces(self):
        regions = load_regions()
        self.assertEqual(len(regions), 81)
        self.assertEqual(set(regions), set(self.frame["key"]))

    def test_demographic_shares_are_fractions(self):
        for column in [
            "female_share", "hh_1_2", "hh_3_4", "hh_5plus",
            "edu_primary", "edu_secondary", "edu_high_school", "edu_university",
        ]:
            self.assertGreaterEqual(self.frame[column].min(), 0.0)
            self.assertLessEqual(self.frame[column].max(), 1.0)

    def test_correlations_cover_every_pair(self):
        correlations = compute_correlations(self.frame)
        self.assertEqual(len(correlations), len(OUTCOMES) * len(DEMOGRAPHICS))
        self.assertTrue(correlations["pearson_r"].between(-1, 1).all())
        self.assertTrue(correlations["spearman_rho"].between(-1, 1).all())
        self.assertTrue(correlations["partial_r"].between(-1, 1).all())

    def test_web_payload_has_all_rows(self):
        correlations = compute_correlations(self.frame)
        payload = build_web_payload(self.frame, correlations)
        self.assertEqual(payload["meta"]["n"], 81)
        self.assertEqual(len(payload["provinces"]), 81)
        self.assertEqual(
            len(payload["correlations"]), len(OUTCOMES) * len(DEMOGRAPHICS)
        )

    def test_province_names_normalize_across_sources(self):
        self.assertEqual(
            normalize_province("AFYONKARAH\u0130SAR"),
            normalize_province("AFYONKARAHISAR"),
        )
        self.assertEqual(
            normalize_province("HAKK\u00c2RI"),
            normalize_province("HAKKARI"),
        )


if __name__ == "__main__":
    unittest.main()
