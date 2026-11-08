import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "data" / "2024_local_actuals.csv"
SHARES = ["CHP", "AKP", "MHP", "IYI", "HDP_DEM", "YRP", "ZP", "SP", "BBP", "TIP", "OTHER"]


class TestLocalActuals2024(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = pd.read_csv(PATH)

    def test_covers_cities_and_districts(self):
        self.assertEqual(len(self.frame), 1054)
        self.assertEqual((self.frame["scope_type"] == "city").sum(), 81)
        self.assertEqual((self.frame["scope_type"] == "district").sum(), 973)

    def test_shares_sum_to_one(self):
        totals = self.frame[SHARES].sum(axis=1)
        self.assertTrue(((totals - 1).abs() < 1e-9).all())
        self.assertTrue(self.frame[SHARES].ge(0).all().all())

    def test_known_winners_are_plausible(self):
        rows = self.frame[self.frame["key"].isin(["ISTANBUL", "ANKARA", "DIYARBAKIR", "BILECIK"])]
        winners = {
            row["key"]: max(SHARES, key=lambda party: row[party])
            for _, row in rows.iterrows()
        }
        self.assertEqual(winners["ISTANBUL"], "CHP")
        self.assertEqual(winners["ANKARA"], "CHP")
        self.assertEqual(winners["DIYARBAKIR"], "HDP_DEM")
        self.assertEqual(winners["BILECIK"], "CHP")


if __name__ == "__main__":
    unittest.main()
