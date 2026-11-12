import unittest

from pipeline.forecast_model import (
    PARTIES,
    REFERENCE,
    bootstrap,
    calibrated_error_scales,
    fit_once,
    normalize,
    shares_from_log_ratios,
)


def poll(pollster, date, shares):
    return {"pollster": pollster, "date": date, "sample_size": 1000, "shares": shares}


class TestForecastModel(unittest.TestCase):
    def test_normalize_folds_to_one(self):
        self.assertEqual(
            normalize({"P9": 2, "P21": 1, "P11": None}), {"P9": 2 / 3, "P21": 1 / 3}
        )

    def test_log_ratio_round_trip(self):
        shares = shares_from_log_ratios({"P21": -0.2, "P11": -1.0})
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        self.assertGreater(shares[REFERENCE], shares["P21"])
        self.assertGreater(shares["P21"], shares["P11"])

    def test_fit_absorbs_a_pollster_house_effect(self):
        polls = [
            poll("Fair", "2024-01-02", {"P9": 0.40, "P21": 0.30, "OTHER": 0.30}),
            poll("Fair", "2024-01-03", {"P9": 0.40, "P21": 0.30, "OTHER": 0.30}),
            poll("Bias", "2024-01-02", {"P9": 0.50, "P21": 0.20, "OTHER": 0.30}),
            poll("Bias", "2024-01-03", {"P9": 0.50, "P21": 0.20, "OTHER": 0.30}),
        ]
        fit = fit_once(polls, "2024-01-04", 3650, 0.0)
        self.assertIn("Bias", fit.house_effects)
        self.assertTrue(fit.house_effects["Bias"]["P21"] < 0)
        self.assertAlmostEqual(sum(fit.shares.values()), 1.0)

    def test_error_scales_are_calibrated(self):
        scales = calibrated_error_scales()
        self.assertTrue(all(value > 0 for value in scales.values()))
        self.assertGreater(scales["P9"], scales["P21"])

    def test_bootstrap_is_deterministic(self):
        polls = [
            poll("A", "2024-01-02", {"P9": 0.4, "P21": 0.6}),
            poll("B", "2024-01-03", {"P9": 0.45, "P21": 0.55}),
        ]
        left, _ = bootstrap(polls, "2024-01-04", 3650, 0.0, 20, seed=7)
        right, _ = bootstrap(polls, "2024-01-04", 3650, 0.0, 20, seed=7)
        self.assertEqual(left.shape[1], len(PARTIES))
        self.assertTrue((left == right).all())


if __name__ == "__main__":
    unittest.main()
