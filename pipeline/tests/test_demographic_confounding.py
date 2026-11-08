import unittest
from pathlib import Path

import pandas as pd

from pipeline.demographic_confounding import build_diagnostics

ROOT = Path(__file__).resolve().parents[2]


class TestDemographicConfounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frame = pd.read_csv(ROOT / "data" / "analysis" / "province_demographics.csv")
        cls.vif, cls.pairwise, cls.fits, cls.stability = build_diagnostics(frame)

    def test_vif_is_defined(self):
        self.assertEqual(len(self.vif), 9)
        self.assertTrue((self.vif["vif"] >= 1).all())
        self.assertTrue(pd.isna(self.vif["vif"]).sum() == 0)

    def test_pairwise_grid_is_complete(self):
        self.assertEqual(len(self.pairwise), 36)
        self.assertTrue(self.pairwise["pearson_r"].between(-1, 1).all())

    def test_swing_fits_are_bounded(self):
        self.assertEqual(len(self.fits), 6)
        self.assertTrue(self.fits["r2"].between(0, 1).all())

    def test_region_stability_is_bounded(self):
        self.assertEqual(len(self.stability), 9)
        self.assertTrue(self.stability["stability"].between(0, 1).all())


if __name__ == "__main__":
    unittest.main()
