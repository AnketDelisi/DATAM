import unittest

from pipeline.district_swing import MAX_LOG_DEVIATION, build


class TestDistrictSwing(unittest.TestCase):
    def test_build_covers_districts_and_clips(self):
        payload = build()
        self.assertEqual(len(payload["districts"]), 87)
        values = [
            value for row in payload["districts"].values() for value in row.values()
        ]
        self.assertTrue(values)
        self.assertLessEqual(max(abs(value) for value in values), MAX_LOG_DEVIATION)


if __name__ == "__main__":
    unittest.main()
