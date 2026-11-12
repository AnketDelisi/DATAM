import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "parliament_2018_districts.csv"


class Test2018Districts(unittest.TestCase):
    def test_aggregate_has_87_districts_and_600_seats(self):
        with open(DATA, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 87)
        self.assertEqual(sum(int(row["seats"]) for row in rows), 600)
        self.assertGreater(sum(int(row["valid_votes"]) for row in rows), 40_000_000)


if __name__ == "__main__":
    unittest.main()
