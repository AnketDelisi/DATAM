import unittest
from pathlib import Path

import pandas as pd

from pipeline.demographic_swing_backtest import loo_predictions, score

ROOT = Path(__file__).resolve().parents[2]


class TestDemographicSwingBacktest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frame = pd.read_csv(ROOT / "data" / "analysis" / "province_demographics.csv")
        cls.predictions = loo_predictions(frame)
        cls.scores = score(cls.predictions)

    def test_loo_covers_every_province(self):
        self.assertEqual(len(self.predictions), 81)
        self.assertTrue(self.predictions[["actual", "uniform", "demographic"]].notna().all().all())

    def test_strength_grid_is_complete(self):
        self.assertEqual(len(self.scores), 11)
        self.assertEqual(self.scores["strength"].min(), 0.0)
        self.assertEqual(self.scores["strength"].max(), 1.0)
        self.assertTrue((self.scores["mae"] > 0).all())


if __name__ == "__main__":
    unittest.main()
