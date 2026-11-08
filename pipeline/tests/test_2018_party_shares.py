import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "data" / "2018_party_shares.csv"
SHARES = ["AKP", "CHP", "MHP", "HDP_DEM", "IYI", "OTHER"]


class TestPartyShares2018(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = pd.read_csv(PATH)

    def test_covers_all_provinces(self):
        self.assertEqual(len(self.frame), 81)
        self.assertEqual(self.frame["key"].nunique(), 81)

    def test_shares_sum_to_one(self):
        totals = self.frame[SHARES].sum(axis=1)
        self.assertTrue(((totals - 1).abs() < 1e-9).all())
        self.assertTrue(self.frame[SHARES].ge(0).all().all())

    def test_kurdish_provinces_are_plausible(self):
        top = set(self.frame.nlargest(10, "HDP_DEM")["key"])
        self.assertIn("SIRNAK", top)
        self.assertIn("HAKKARI", top)
        self.assertIn("DIYARBAKIR", top)


if __name__ == "__main__":
    unittest.main()
