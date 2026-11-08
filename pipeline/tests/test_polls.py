import unittest
from pathlib import Path

from pipeline.validate_polls import validate_dataset

ROOT = Path(__file__).resolve().parents[2]


class TestPollData(unittest.TestCase):
    def test_scraped_polls_are_valid(self):
        total, errors, counts, _ = validate_dataset(ROOT / "polls")
        self.assertEqual(errors, [])
        self.assertGreaterEqual(total, 145)
        self.assertGreaterEqual(counts[("presidential", 1)], 82)
        self.assertGreaterEqual(counts[("presidential", 2)], 14)
        self.assertGreaterEqual(counts[("parliamentary", None)], 49)


if __name__ == "__main__":
    unittest.main()
