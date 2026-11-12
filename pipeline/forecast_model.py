"""Probabilistic national poll model and district seat projection.

The model estimates a latent party-support path from published polls while
jointly estimating pollster house effects.  It is deliberately small enough
to audit:

    log(share_p / share_ref) = local_linear_trend_p(t) + house_effect_{j,p}

The trend is fitted by backfitting; pollster effects are shrunk toward zero.
Uncertainty comes from a pollster-cluster bootstrap.  District votes use a
proportional swing from the 2023 baseline, then D'Hondt is run per district.

    python pipeline/forecast_model.py
    python pipeline/forecast_model.py --backtest
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from pipeline.allocate import allocate_districts
from pipeline.house_effects import aggregate as aggregate_polls

ROOT = Path(__file__).resolve().parent.parent
PARLIAMENT_POLLS = ROOT / "polls" / "2023_parliament.json"
DISTRICT_DATA = ROOT / "web" / "data" / "parliament_2023.json"
ACTUAL_SEATS = ROOT / "data" / "processed" / "actual_seats_2023.csv"
ALLIANCES = ROOT / "config" / "alliances_2023.yaml"
ELECTIONS = ROOT / "config" / "elections.yaml"
WEB_OUT = ROOT / "web" / "data" / "forecast_2023.json"
ANALYSIS_OUT = ROOT / "data" / "analysis" / "forecast_2023.md"

PARTIES = ["P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24", "P8", "OTHER"]
REFERENCE = "P9"
EPS = 1e-6
MAX_LOG_EFFECT = 0.7
DEFAULT_HALF_LIFE_DAYS = 60.0
DEFAULT_SHRINK_PRIOR = 1.5
DEFAULT_BOOTSTRAP = 400
DEFAULT_ELECTION_ERROR = 0.022
DEFAULT_PRIOR_WEIGHT = 2.0
DEFAULT_THRESHOLD = 0.07
DEFAULT_CUTOFF = "2023-05-14"
HISTORICAL = ROOT / "polls" / "historical"
CALIBRATION_ELECTIONS = ["2015-06", "2015-11", "2018-general"]
HISTORICAL_TO_PARTY = {
    "AKP": "P9",
    "CHP": "P21",
    "MHP": "P11",
    "IYI": "P22",
    "HDP_DEM": "P12",
    "YRP": "P10",
    "TIP": "P13",
    "ZP": "P24",
    "BBP": "P8",
}


def normalize(values: dict[str, float], total: float | None = None) -> dict[str, float]:
    clean = {key: float(value) for key, value in values.items() if value and value > 0}
    denominator = total if total is not None else sum(clean.values())
    if denominator <= 0:
        return {}
    return {key: value / denominator for key, value in clean.items()}


def poll_shares(poll: dict, parties: list[str]) -> dict[str, float]:
    """Normalize one poll, folding unlisted parties into OTHER."""
    known = set(parties) - {"OTHER"}
    shares = {}
    for key, value in poll.get("results", {}).items():
        if value is None or value <= 0:
            continue
        target = key if key in known else "OTHER"
        shares[target] = shares.get(target, 0.0) + float(value)
    return normalize(shares)


def load_polls(path: Path, parties: list[str], cutoff: str | None = None) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    polls = []
    for poll in payload.get("polls", []):
        if cutoff and poll["field_end"] > cutoff:
            continue
        shares = poll_shares(poll, parties)
        if shares.get(REFERENCE, 0.0) <= 0:
            continue
        polls.append(
            {
                "pollster": poll["pollster"],
                "date": poll["field_end"],
                "sample_size": poll.get("sample_size") or 1000,
                "shares": shares,
            }
        )
    return polls


def calibrated_error_scales() -> dict[str, float]:
    """Estimate party-level polling-error scales from pre-2023 elections."""
    cfg = yaml.safe_load(ELECTIONS.read_text(encoding="utf-8"))["elections"]
    errors: dict[str, list[float]] = {}
    all_errors = []
    for election_id in CALIBRATION_ELECTIONS:
        path = HISTORICAL / f"{election_id}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual = cfg[election_id]["races"]["parliamentary"]["actual"]
        result = aggregate_polls(payload["polls"], list(actual), cutoff=cfg[election_id]["date"])
        for entity, value in actual.items():
            party = HISTORICAL_TO_PARTY.get(entity)
            if not party:
                continue
            error = result.get(entity, 0.0) - value
            errors.setdefault(party, []).append(error)
            all_errors.append(error)
    global_rmse = (
        math.sqrt(sum(value**2 for value in all_errors) / len(all_errors))
        if all_errors
        else DEFAULT_ELECTION_ERROR
    )
    scales = {}
    for party in PARTIES:
        values = errors.get(party, [])
        if not values:
            scales[party] = global_rmse
            continue
        rmse = math.sqrt(sum(value**2 for value in values) / len(values))
        shrink = len(values) / (len(values) + 2.0)
        scales[party] = max(0.008, global_rmse + (rmse - global_rmse) * shrink)
    return scales


def effective_day(poll_date: str, reference_date: str) -> float:
    return (date.fromisoformat(poll_date) - date.fromisoformat(reference_date)).days


def poll_weight(poll: dict, reference_date: str, half_life_days: float) -> float:
    age = max(0, -effective_day(poll["date"], reference_date))
    recency = 0.5 ** (age / half_life_days)
    sample = math.sqrt(max(1.0, float(poll.get("sample_size") or 1000)) / 1000.0)
    return recency * sample


def weighted_line(rows: list[tuple[float, float, float]]) -> tuple[float, float] | None:
    """Weighted local linear intercept/slope at day 0."""
    if not rows:
        return None
    weights = np.asarray([row[2] for row in rows], dtype=float)
    x = np.asarray([row[0] for row in rows], dtype=float)
    y = np.asarray([row[1] for row in rows], dtype=float)
    if len(rows) == 1 or float(np.ptp(x)) < 0.5:
        return float(np.average(y, weights=weights)), 0.0
    design = np.column_stack([np.ones_like(x), x])
    normal = design.T @ (design * weights[:, None])
    rhs = design.T @ (y * weights)
    try:
        beta = np.linalg.solve(normal, rhs)
    except np.linalg.LinAlgError:
        return float(np.average(y, weights=weights)), 0.0
    return float(beta[0]), float(beta[1])


def shrink_effect(
    mean: float,
    effective_n: float,
    prior: float,
    prior_mean: float = 0.0,
    prior_weight: float = 0.0,
) -> float:
    total_n = effective_n + prior_weight
    if total_n <= 0:
        return 0.0
    combined = (mean * effective_n + prior_mean * prior_weight) / total_n
    value = combined * (total_n / (total_n + prior))
    return max(-MAX_LOG_EFFECT, min(MAX_LOG_EFFECT, value))


@dataclass
class Fit:
    shares: dict[str, float]
    log_ratios: dict[str, float]
    house_effects: dict[str, dict[str, float]] = field(default_factory=dict)
    effective_n: dict[str, float] = field(default_factory=dict)


def fit_once(
    polls: list[dict],
    reference_date: str,
    half_life_days: float,
    shrink_prior: float,
    iterations: int = 8,
    prior_effects: dict[str, dict[str, float]] | None = None,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
) -> Fit:
    parties = [party for party in PARTIES if party != REFERENCE]
    effects: dict[str, dict[str, float]] = {}
    trend: dict[str, tuple[float, float]] = {}
    effective_n: dict[str, float] = {}

    for _ in range(iterations):
        for party in parties:
            rows = []
            for poll in polls:
                shares = poll["shares"]
                if shares.get(party, 0.0) <= 0 or shares.get(REFERENCE, 0.0) <= 0:
                    continue
                effect = effects.get(poll["pollster"], {}).get(party, 0.0)
                y = math.log(shares[party] / shares[REFERENCE]) - effect
                weight = poll_weight(poll, reference_date, half_life_days)
                rows.append((effective_day(poll["date"], reference_date), y, weight))
            result = weighted_line(rows)
            if result:
                trend[party] = result

        next_effects: dict[str, dict[str, float]] = {}
        for party in parties:
            by_pollster: dict[str, list[tuple[float, float]]] = {}
            for poll in polls:
                shares = poll["shares"]
                if shares.get(party, 0.0) <= 0 or shares.get(REFERENCE, 0.0) <= 0:
                    continue
                intercept, slope = trend.get(party, (0.0, 0.0))
                dt = effective_day(poll["date"], reference_date)
                residual = math.log(shares[party] / shares[REFERENCE]) - (intercept + slope * dt)
                weight = poll_weight(poll, reference_date, half_life_days)
                by_pollster.setdefault(poll["pollster"], []).append((residual, weight))
            for pollster, rows in by_pollster.items():
                total_weight = sum(weight for _, weight in rows)
                if total_weight <= 0:
                    continue
                mean = sum(value * weight for value, weight in rows) / total_weight
                n = total_weight**2 / sum(weight**2 for _, weight in rows)
                prior_mean = (prior_effects or {}).get(pollster, {}).get(party, 0.0)
                next_effects.setdefault(pollster, {})[party] = shrink_effect(
                    mean, n, shrink_prior, prior_mean, prior_weight
                )
                if party not in effective_n or n > effective_n[party]:
                    effective_n[party] = n
        effects = next_effects

    log_ratios = {party: trend.get(party, (0.0, 0.0))[0] for party in parties}
    shares = shares_from_log_ratios(log_ratios)
    return Fit(shares=shares, log_ratios=log_ratios, house_effects=effects, effective_n=effective_n)


def shares_from_log_ratios(log_ratios: dict[str, float]) -> dict[str, float]:
    exp_values = {party: math.exp(max(-10.0, min(10.0, value))) for party, value in log_ratios.items()}
    reference_share = 1.0 / (1.0 + sum(exp_values.values()))
    shares = {REFERENCE: reference_share}
    for party, value in exp_values.items():
        shares[party] = reference_share * value
    return normalize(shares)


def bootstrap(
    polls: list[dict],
    reference_date: str,
    half_life_days: float,
    shrink_prior: float,
    draws: int,
    seed: int = 2023,
    prior_effects: dict[str, dict[str, float]] | None = None,
) -> tuple[np.ndarray, list[Fit]]:
    rng = random.Random(seed)
    by_pollster: dict[str, list[dict]] = {}
    for poll in polls:
        by_pollster.setdefault(poll["pollster"], []).append(poll)
    names = sorted(by_pollster)
    rows = []
    fits = []
    for _ in range(draws):
        selected = []
        for _ in range(len(names)):
            selected.extend(by_pollster[rng.choice(names)])
        fit = fit_once(
            selected,
            reference_date,
            half_life_days,
            shrink_prior,
            prior_effects=prior_effects,
        )
        values = [fit.shares.get(party, 0.0) for party in PARTIES]
        if sum(values) > 0:
            rows.append(values)
            fits.append(fit)
    return np.asarray(rows, dtype=float), fits


def summarize(draws: np.ndarray) -> dict[str, dict[str, float]]:
    result = {}
    for index, party in enumerate(PARTIES):
        values = draws[:, index] if len(draws) else np.empty(0)
        if not len(values):
            continue
        result[party] = {
            "mean": round(float(values.mean()), 6),
            "p05": round(float(np.quantile(values, 0.05)), 6),
            "p50": round(float(np.quantile(values, 0.50)), 6),
            "p95": round(float(np.quantile(values, 0.95)), 6),
        }
    return result


def load_districts() -> list[dict]:
    payload = json.loads(DISTRICT_DATA.read_text(encoding="utf-8"))
    districts = []
    for row in payload["districts"]:
        votes = {party: float(row["votes"].get(party, 0.0)) for party in PARTIES if party != "OTHER"}
        total = sum(votes.values())
        if total <= 0:
            continue
        other = max(0.0, 1.0 - sum(votes.values()) / total)
        shares = {party: value / total for party, value in votes.items()}
        shares["OTHER"] = other
        districts.append(
            {
                "id": row["id"],
                "province": row["province"],
                "seats": int(row["seats"]),
                "weight": float(row.get("valid_votes") or total),
                "shares": normalize(shares),
            }
        )
    return districts


def baseline_national(districts: list[dict]) -> dict[str, float]:
    votes = {party: 0.0 for party in PARTIES}
    for district in districts:
        weight = district.get("weight", 1.0)
        for party in PARTIES:
            votes[party] += district["shares"].get(party, 0.0) * weight
    return normalize(votes)


def allocate_from_shares(
    national_shares: dict[str, float],
    districts: list[dict],
    baseline: dict[str, float],
    alliances: dict[str, list[str]],
    threshold: float,
    province_swing: dict[str, dict[str, float]] | None = None,
) -> dict[str, int]:
    factors = {
        party: (national_shares.get(party, 0.0) / baseline[party])
        if baseline.get(party, 0.0) > 0
        else 0.0
        for party in PARTIES
    }
    district_votes = {}
    district_seats = {}
    national_votes = {party: 0 for party in PARTIES}
    for district in districts:
        projected = {}
        local = (province_swing or {}).get(district["province"], {})
        for party in PARTIES:
            projected[party] = int(
                round(
                    district["shares"].get(party, 0.0)
                    * factors.get(party, 0.0)
                    * math.exp(local.get(party, 0.0))
                    * 1_000_000
                )
            )
        projected = {party: max(0, value) for party, value in projected.items()}
        total = sum(projected.values())
        if total <= 0:
            continue
        district_votes[district["id"]] = projected
        district_seats[district["id"]] = district["seats"]
        for party, value in projected.items():
            national_votes[party] += value
    by_district, _ = allocate_districts(
        district_votes, district_seats, national_votes, alliances, threshold
    )
    totals = {party: 0 for party in PARTIES}
    for result in by_district.values():
        for party, seats in result.items():
            totals[party] = totals.get(party, 0) + seats
    return totals


def actual_seats() -> dict[str, int]:
    import csv

    result = {}
    with open(ACTUAL_SEATS, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            result[row["party_id"]] = int(row["seats"])
    return result


def actual_national() -> dict[str, float]:
    payload = json.loads(
        (ROOT / "web" / "data" / "parliament_2023.json").read_text(encoding="utf-8")
    )
    shares = {
        party: float(value)
        for party, value in payload["national"]["shares"].items()
        if party in PARTIES and party != "OTHER"
    }
    shares["OTHER"] = max(0.0, 1.0 - sum(shares.values()))
    return shares


HOUSE_PRIOR = ROOT / "web" / "data" / "house_effects_2019.json"
PARTY_TO_HISTORICAL = {
    "P9": "AKP",
    "P21": "CHP",
    "P11": "MHP",
    "P22": "IYI",
    "P12": "HDP_DEM",
    "P10": "YRP",
    "P13": "TIP",
    "P24": "ZP",
    "P8": "BBP",
}


def load_house_prior() -> dict[str, dict[str, float]]:
    if not HOUSE_PRIOR.exists():
        return {}
    payload = json.loads(HOUSE_PRIOR.read_text(encoding="utf-8"))
    prior = {}
    for pollster, effect in payload.get("pollsters", {}).items():
        total = effect.get("total_effects", {})
        priors = {}
        for party, historical in PARTY_TO_HISTORICAL.items():
            if party == REFERENCE:
                continue
            value = total.get(historical)
            if value is not None:
                priors[party] = float(value)
        if priors:
            prior[pollster] = priors
    return prior


def load_alliances() -> tuple[dict[str, list[str]], float]:
    cfg = yaml.safe_load(ALLIANCES.read_text(encoding="utf-8"))
    alliances = {name: list(members) for name, members in cfg["alliances"].items()}
    return alliances, float(cfg["threshold"])


def fit_forecast(
    cutoff: str,
    draws: int = DEFAULT_BOOTSTRAP,
    seed: int = 2023,
    use_historical_prior: bool = False,
    election_error: float | dict[str, float] | None = None,
) -> dict:
    if election_error is None:
        election_error = calibrated_error_scales()
    polls = load_polls(PARLIAMENT_POLLS, PARTIES, cutoff)
    if not polls:
        raise SystemExit(f"no parliamentary polls before {cutoff}")
    reference_date = max(poll["date"] for poll in polls)
    prior = load_house_prior() if use_historical_prior else {}
    point = fit_once(
        polls,
        reference_date,
        DEFAULT_HALF_LIFE_DAYS,
        DEFAULT_SHRINK_PRIOR,
        prior_effects=prior,
    )
    samples, _ = bootstrap(
        polls,
        reference_date,
        DEFAULT_HALF_LIFE_DAYS,
        DEFAULT_SHRINK_PRIOR,
        draws,
        seed,
        prior_effects=prior,
    )
    if len(samples):
        rng = np.random.default_rng(seed + 1)
        if isinstance(election_error, dict):
            scales = np.asarray(
                [
                    max(0.0, float(election_error.get(party, DEFAULT_ELECTION_ERROR)))
                    for party in PARTIES
                ]
            )
        else:
            scales = np.full(len(PARTIES), max(0.0, float(election_error)))
        if scales.max() > 0:
            noisy = []
            for sample in samples:
                values = np.asarray(sample, dtype=float) + rng.normal(0.0, scales)
                values = np.clip(values, EPS, None)
                noisy.append(values / values.sum())
            samples = np.asarray(noisy, dtype=float)
    summary = summarize(samples)
    districts = load_districts()
    baseline = baseline_national(districts)
    alliances, threshold = load_alliances()
    seat_draws = []
    for sample in samples:
        shares = {party: float(sample[index]) for index, party in enumerate(PARTIES)}
        seat_draws.append(
            allocate_from_shares(shares, districts, baseline, alliances, threshold)
        )
    seats = {
        party: {
            "mean": round(float(np.mean([row.get(party, 0) for row in seat_draws])), 2),
            "p05": int(np.quantile([row.get(party, 0) for row in seat_draws], 0.05)),
            "p50": int(np.quantile([row.get(party, 0) for row in seat_draws], 0.50)),
            "p95": int(np.quantile([row.get(party, 0) for row in seat_draws], 0.95)),
        }
        for party in PARTIES
    }
    return {
        "meta": {
            "method": "latent log-ratio local trend + shrunk pollster effects + cluster bootstrap",
            "cutoff": cutoff,
            "reference_date": reference_date,
            "half_life_days": DEFAULT_HALF_LIFE_DAYS,
            "shrink_prior_polls": DEFAULT_SHRINK_PRIOR,
            "bootstrap_draws": len(samples),
            "poll_count": len(polls),
            "pollster_count": len({poll["pollster"] for poll in polls}),
            "election_error_scale": (
                election_error
                if isinstance(election_error, dict)
                else {"all": election_error}
            ),
            "historical_house_prior": use_historical_prior,
            "note": "Pollster effects are estimated jointly against the latent trend, not applied post-hoc. Election error is calibrated separately from historical polling misses.",
        },
        "point": {
            "shares": {party: round(value, 6) for party, value in point.shares.items()},
            "log_ratios": {party: round(value, 6) for party, value in point.log_ratios.items()},
        },
        "national": summary,
        "seats": seats,
        "district_baseline": baseline,
        "house_effects": {
            pollster: {party: round(value, 6) for party, value in effects.items()}
            for pollster, effects in point.house_effects.items()
        },
    }


def backtest(cutoff: str = DEFAULT_CUTOFF, draws: int = DEFAULT_BOOTSTRAP) -> dict:
    forecast = fit_forecast(cutoff, draws)
    actual = actual_national()
    seat_actual = actual_seats()
    national_errors = {
        party: abs(forecast["point"]["shares"].get(party, 0.0) - actual.get(party, 0.0))
        for party in PARTIES
        if party in actual
    }
    seat_errors = {
        party: abs(
            forecast["seats"][party]["mean"] - seat_actual.get(party, 0)
        )
        for party in PARTIES
        if party in seat_actual
    }
    covered = [
        forecast["national"][party]["p05"]
        <= actual.get(party, 0.0)
        <= forecast["national"][party]["p95"]
        for party in PARTIES
        if party in actual and party in forecast["national"]
    ]
    return {
        "cutoff": cutoff,
        "national_mae": float(np.mean(list(national_errors.values()))),
        "seat_mae": float(np.mean(list(seat_errors.values()))),
        "coverage_90": float(np.mean(covered)) if covered else 0.0,
        "national_errors": national_errors,
        "seat_errors": seat_errors,
        "forecast": forecast,
    }


def write_backtest_report(result: dict) -> None:
    ANALYSIS_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 2023 probabilistic forecast backtest",
        "",
        f"- Cutoff: {result['cutoff']}",
        f"- National MAE: {result['national_mae']:.4f}",
        f"- Seat MAE: {result['seat_mae']:.2f}",
        f"- 90% interval coverage: {result['coverage_90']:.1%}",
        "",
        "| Party | Actual | Point | 90% interval | Error |",
        "|---|---:|---:|---:|---:|",
    ]
    actual = actual_national()
    forecast = result["forecast"]
    for party in PARTIES:
        if party not in actual:
            continue
        row = forecast["national"].get(party, {})
        lines.append(
            f"| {party} | {actual[party]:.4f} | {row.get('p50', 0):.4f} | "
            f"{row.get('p05', 0):.4f}–{row.get('p95', 0):.4f} | "
            f"{result['national_errors'].get(party, 0):.4f} |"
        )
    ANALYSIS_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--draws", type=int, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--seed", type=int, default=2023)
    parser.add_argument("--out", type=Path, default=WEB_OUT)
    args = parser.parse_args()

    if args.backtest:
        result = backtest(args.cutoff, args.draws)
        write_backtest_report(result)
        print(
            f"cutoff={result['cutoff']} national_mae={result['national_mae']:.4f} "
            f"seat_mae={result['seat_mae']:.2f} coverage={result['coverage_90']:.1%}"
        )
        return

    payload = fit_forecast(args.cutoff, args.draws, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {args.out.relative_to(ROOT)} ({payload['meta']['poll_count']} polls)")


if __name__ == "__main__":
    main()
