import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "data" / "parliament_2023.json"


class TestSiteParties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parties = {
            party["id"]: party
            for party in json.loads(DATA.read_text(encoding="utf-8"))["parties"]
        }

    def test_new_parties_are_registered_for_2028(self):
        for party_id in ("YENI", "A"):
            party = self.parties[party_id]
            self.assertEqual(party["active_from"], 2028)
            self.assertTrue(party["main"])
            self.assertTrue(party["baseline_mix"])

    def test_2023_main_parties_are_unchanged(self):
        for party_id in ("P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24"):
            self.assertTrue(self.parties[party_id]["main"])
            self.assertIsNone(self.parties[party_id].get("active_from"))


if __name__ == "__main__":
    unittest.main()
