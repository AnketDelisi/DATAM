import unittest
from datetime import date

from pipeline.house_effects import Model, apply_effect_set


class TestHouseEffects(unittest.TestCase):
    def setUp(self):
        self.entities = {
            "parties": {
                "A": {"name": "A", "aliases": [], "bloc": "INCUMBENT"},
                "B": {"name": "B", "aliases": [], "bloc": "OPPOSITION"},
            },
            "candidates": {},
        }
        self.cfg = {
            "half_life_days": 3650,
            "min_effective_polls": 1,
            "shrink_prior_polls": 0,
            "local_bloc_only": True,
            "election_type_weights": {"general": 1.0},
            "race_type_weights": {"parliamentary": 1.0},
        }
        base = {
            "election_id": "e",
            "type": "general",
            "race": "parliamentary",
            "race_type": "parliamentary",
            "scope": "national",
            "scope_type": "national",
            "field_end": "2024-01-01",
            "sample_size": 1000,
        }
        self.polls = [
            {**base, "pollster": "Fair", "results": {"A": 0.5, "B": 0.5}},
            {**base, "pollster": "Fair", "results": {"A": 0.5, "B": 0.5}},
            {**base, "pollster": "Bias", "results": {"A": 0.7, "B": 0.3}},
            {**base, "pollster": "Bias", "results": {"A": 0.7, "B": 0.3}},
        ]

    def test_bias_is_detected_and_corrected(self):
        model = Model(self.polls, self.entities, self.cfg, date(2024, 1, 2))
        effects = model.fit()
        bias = effects["Bias"]["bloc_effects"]["OPPOSITION"]
        self.assertLess(bias, 0)
        adjusted = apply_effect_set({"A": 0.7, "B": 0.3}, effects["Bias"], model.bloc_of)
        self.assertLess(adjusted["A"], 0.7)
        self.assertGreater(adjusted["B"], 0.3)
        self.assertAlmostEqual(sum(adjusted.values()), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
