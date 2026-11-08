import json
import unittest
from pathlib import Path

import pandas as pd

from pipeline.project_2028_seats import load_config, project_seats

ROOT = Path(__file__).resolve().parents[2]


class Test2028Seats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = pd.read_csv(
            ROOT / "data" / "processed" / "parliament_2023_districts.csv"
        )
        cls.cfg = load_config()

    def test_imported_600_seat_numbers(self):
        projected = project_seats(self.frame, self.cfg)
        self.assertEqual(int(projected["seats"].sum()), 600)
        seats = dict(zip(projected["district_id"], projected["seats"]))
        self.assertEqual(seats["34_404601"], 25)
        self.assertEqual(seats["6_404520"], 13)
        self.assertEqual(seats["16_404560"], 11)

    def test_uniform_growth_falls_back_to_2023_seats(self):
        cfg = dict(self.cfg)
        cfg.pop("district_seats", None)
        projected = project_seats(self.frame, cfg)
        self.assertEqual(int(projected["seats"].sum()), 600)
        self.assertTrue((projected["seats"] == projected["base_seats"]).all())

    def test_override_preserves_total_and_minimum(self):
        cfg = dict(self.cfg)
        cfg["province_annual_growth"] = {"ISTANBUL": 0.05}
        projected = project_seats(self.frame, cfg)
        self.assertEqual(int(projected["seats"].sum()), 600)
        self.assertTrue((projected["seats"] >= 1).all())
        self.assertTrue((projected["seats"] != projected["base_seats"]).any())

    def test_published_projection_has_all_districts(self):
        payload = json.loads(
            (ROOT / "web" / "data" / "seat_projection_2028.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(sum(payload["districts"].values()), 600)
        self.assertEqual(set(payload["districts"]), set(self.frame["district_id"]))


if __name__ == "__main__":
    unittest.main()
