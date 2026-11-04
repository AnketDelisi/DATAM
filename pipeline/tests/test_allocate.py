import unittest

from pipeline.allocate import allocate, dhondt, qualifying_parties


class TestDhondt(unittest.TestCase):
    def test_basic(self):
        got = dhondt({"A": 100, "B": 50, "C": 25}, 3, {"A", "B", "C"})
        self.assertEqual(got, {"A": 2, "B": 1, "C": 0})

    def test_single_seat(self):
        got = dhondt({"A": 10, "B": 9}, 1, {"A", "B"})
        self.assertEqual(got, {"A": 1, "B": 0})

    def test_zero_seats(self):
        self.assertEqual(dhondt({"A": 10}, 0, {"A"}), {"A": 0})

    def test_empty_eligible(self):
        self.assertEqual(dhondt({"A": 10}, 3, set()), {})

    def test_zero_votes(self):
        got = dhondt({"A": 0, "B": 0}, 2, {"A", "B"})
        self.assertEqual(got["A"] + got["B"], 2)


class TestThreshold(unittest.TestCase):
    def test_individual(self):
        got, _ = qualifying_parties({"A": 70, "B": 20, "C": 10}, {}, 0.25)
        self.assertEqual(got, {"A"})

    def test_alliance_lifts_small_party(self):
        got, shares = qualifying_parties(
            {"A": 70, "B": 3, "C": 27}, {"X": ["B", "C"]}, 0.10
        )
        self.assertEqual(got, {"A", "B", "C"})
        self.assertAlmostEqual(shares["X"], 0.30)

    def test_alliance_below_threshold(self):
        got, _ = qualifying_parties(
            {"A": 70, "B": 2, "C": 2}, {"X": ["B", "C"]}, 0.10
        )
        self.assertEqual(got, {"A"})

    def test_independent_ignored_by_threshold(self):
        got, _ = qualifying_parties({"A": 70, "I1": 30}, {}, 0.10)
        self.assertEqual(got, {"A"})

    def test_joint_list_counts_for_alliance(self):
        got, shares = qualifying_parties(
            {"A": 70, "B": 2, "A1": 5}, {"X": ["B"]}, 0.07, {"A1": "X"}
        )
        self.assertIn("B", got)
        self.assertIn("A1", got)
        self.assertAlmostEqual(shares["X"], 7 / 77)


class TestAllocation(unittest.TestCase):
    def test_independent_always_eligible(self):
        totals, _ = allocate(
            {"d1": {"P1": 100, "I1": 100}},
            {"d1": 1},
            {"P1": 100, "I1": 100},
            {},
            0.5,
        )
        self.assertEqual(totals.get("P1", 0) + totals.get("I1", 0), 1)

    def test_joint_list_assigned_to_largest(self):
        totals, _ = allocate(
            {"d1": {"P1": 100, "P2": 50, "A1": 200}},
            {"d1": 1},
            {"P1": 100, "P2": 50, "A1": 200},
            {"X": ["P1", "P2"]},
            0.0,
            {"A1": "X"},
        )
        self.assertEqual(totals.get("P1", 0), 1)

    def test_seats_conserved(self):
        totals, _ = allocate(
            {"d1": {"P1": 100, "P2": 50}, "d2": {"P1": 10, "P2": 90}},
            {"d1": 3, "d2": 2},
            {"P1": 110, "P2": 140},
            {},
            0.0,
        )
        self.assertEqual(sum(totals.values()), 5)


if __name__ == "__main__":
    unittest.main()
