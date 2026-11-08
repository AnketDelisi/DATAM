import json
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


class TestKurdishSupportIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = pd.read_csv(ROOT / "data" / "analysis" / "kurdish_support.csv")

    def test_covers_all_provinces(self):
        self.assertEqual(len(self.frame), 81)
        self.assertEqual(self.frame["key"].nunique(), 81)
        self.assertTrue(self.frame["index"].between(0, 1).all())
        self.assertFalse(self.frame[["2015-06", "2015-11", "2018", "2023"]].isna().any().any())

    def test_high_support_provinces_are_plausible(self):
        top = set(self.frame.nlargest(5, "index")["key"])
        self.assertTrue({"SIRNAK", "HAKKARI", "DIYARBAKIR"}.issubset(top))

    def test_published_payload_matches_csv(self):
        payload = json.loads(
            (ROOT / "web" / "data" / "kurdish_support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(payload["provinces"]), 81)
        self.assertEqual(
            {row["key"] for row in payload["provinces"]},
            set(self.frame["key"]),
        )
        self.assertIn("not a Kurdish population estimate", payload["meta"]["note"])
        self.assertEqual(len(payload["ilce"]), 973)
        self.assertTrue(all(0 <= row["index"] <= 1 for row in payload["ilce"]))


if __name__ == "__main__":
    unittest.main()
