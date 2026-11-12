import unittest

from pipeline.province_swing import MAX_LOG_DEVIATION, build


class TestProvinceSwing(unittest.TestCase):
    def test_build_covers_provinces_and_clips_values(self):
        payload = build()
        self.assertGreaterEqual(len(payload["provinces"]), 80)
        values = [
            value for row in payload["provinces"].values() for value in row.values()
        ]
        self.assertTrue(values)
        self.assertLessEqual(max(abs(value) for value in values), MAX_LOG_DEVIATION)


if __name__ == "__main__":
    unittest.main()
