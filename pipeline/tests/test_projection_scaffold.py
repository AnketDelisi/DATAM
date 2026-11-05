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

    def test_2028_poll_file_is_empty_but_valid(self):
        payload = json.loads((WEB / "polls_2028.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["datasets"]["president"]["polls"], [])
        self.assertEqual(payload["datasets"]["parliament"]["polls"], [])

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
