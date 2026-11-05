import json
import unittest
from pathlib import Path

import pandas as pd

from pipeline.demographic_swing import build_swing

ROOT = Path(__file__).resolve().parents[2]


class TestDemographicSwing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frame = pd.read_csv(ROOT / "data" / "analysis" / "province_demographics.csv")
        cls.payload = build_swing(frame)

    def test_scores_cover_all_provinces(self):
        self.assertEqual(self.payload["meta"]["n"], 81)
        self.assertEqual(len(self.payload["provinces"]), 81)
        for values in self.payload["provinces"].values():
            self.assertEqual(set(values), set(self.payload["meta"]["outcomes"]))
            self.assertTrue(all(isinstance(v, (int, float)) for v in values.values()))

    def test_published_provinces_match_analysis(self):
        published = json.loads(
            (ROOT / "web" / "data" / "demographic_swing.json").read_text(encoding="utf-8")
        )
        frame = pd.read_csv(ROOT / "data" / "analysis" / "province_demographics.csv")
        self.assertEqual(set(published["provinces"]), set(frame["key"]))

    def test_scores_are_centered(self):
        frame = pd.read_csv(ROOT / "data" / "analysis" / "province_demographics.csv")
        for outcome in self.payload["meta"]["outcomes"]:
            scores = [self.payload["provinces"][key][outcome] for key in frame["key"]]
            self.assertAlmostEqual(sum(scores) / len(scores), 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
