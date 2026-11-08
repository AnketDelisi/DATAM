import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web" / "data"


class TestProjectionScaffold(unittest.TestCase):
    def test_2028_is_an_explicit_projection(self):
        elections = json.loads((WEB / "elections.json").read_text(encoding="utf-8"))
        election = elections["2028"]
        self.assertEqual(election["status"], "projection")
        self.assertEqual(election["baseline"], "2023")
        self.assertEqual(election["seat_source"], "2028_projection")

    def test_2028_poll_file_is_valid(self):
        payload = json.loads((WEB / "polls_2028.json").read_text(encoding="utf-8"))
        president = payload["datasets"]["president"]["polls"]
        parliament = payload["datasets"]["parliament"]["polls"]
        self.assertGreater(len(president), 0)
        self.assertTrue(any("IMAMOGLU" in poll["results"] for poll in president))
        for poll in president:
            self.assertEqual(poll["type"], "presidential")
            self.assertEqual(poll["round"], 1)
            self.assertGreaterEqual(len(poll["results"]), 2)
        self.assertGreater(len(parliament), 0)
        self.assertTrue(any("YENI" in poll["results"] for poll in parliament))
        self.assertTrue(any("A" in poll["results"] for poll in parliament))
        for poll in parliament:
            self.assertEqual(poll["type"], "parliamentary")
            self.assertIsNone(poll["round"])
            self.assertGreaterEqual(len(poll["results"]), 2)

    def test_demographic_swing_covers_every_province(self):
        swing = json.loads(
            (WEB / "demographic_swing.json").read_text(encoding="utf-8")
        )
        provinces = json.loads(
            (WEB / "demographics.json").read_text(encoding="utf-8")
        )["provinces"]
        self.assertEqual(
            set(swing["provinces"]),
            {row["key"] for row in provinces},
        )


if __name__ == "__main__":
    unittest.main()
