import json
import unittest
from pathlib import Path

from omegaconf import OmegaConf

from pipeline.allocate import allocate, load_inputs

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"


class Test2023Integration(unittest.TestCase):
    def test_600_seats_and_known_residual(self):
        if not (PROCESSED / "parliament_2023_districts.csv").exists():
            self.skipTest("run pipeline/fetch_ysk.py first")

        cfg = OmegaConf.to_container(
            OmegaConf.load(ROOT / "config" / "alliances_2023.yaml"), resolve=True
        )
        alliances = {k: list(v) for k, v in cfg["alliances"].items()}
        joint_lists = dict(cfg.get("joint_lists") or {})
        threshold = float(cfg["threshold"])

        _, actual, district_votes, district_seats, national_votes = load_inputs(
            PROCESSED
        )
        predicted, _ = allocate(
            district_votes,
            district_seats,
            national_votes,
            alliances,
            threshold,
            joint_lists,
        )
        self.assertEqual(sum(predicted.values()), 600)
        self.assertEqual(int(actual["seats"].sum()), 600)

        diffs = []
        for _, row in actual.iterrows():
            diffs.append(abs(predicted.get(row["party_id"], 0) - int(row["seats"])))
        self.assertLessEqual(max(diffs), 2, diffs)

    def test_site_json_has_973_ilce(self):
        path = ROOT / "web" / "data" / "parliament_2023.json"
        if not path.exists():
            self.skipTest("run pipeline/export_site.py first")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["ilce"]), 973)
        self.assertEqual(len({row["geo_id"] for row in data["ilce"]}), 973)
        self.assertTrue(all(row["province"] for row in data["ilce"]))


if __name__ == "__main__":
    unittest.main()
