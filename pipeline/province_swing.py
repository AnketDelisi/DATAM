"""Estimate shrunk province-level swing deviations from 2018 to 2023.

This is a transparent proxy for a district hierarchy: the 87 districts inherit
their province's local swing deviation until district-level historical results
are available.  Values are log deviations from the national swing, shrunk by
province size and clipped to a conservative range.

    python pipeline/province_swing.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from pipeline.demographic_correlation import normalize_province

ROOT = Path(__file__).resolve().parent.parent
PRIOR = ROOT / "data" / "2018_party_shares.csv"
RESULT = ROOT / "web" / "data" / "parliament_2023.json"
OUT = ROOT / "web" / "data" / "province_swing.json"

PARTY_MAP = {
    "P9": "AKP",
    "P21": "CHP",
    "P11": "MHP",
    "P22": "IYI",
    "P12": "HDP_DEM",
}
MAX_LOG_DEVIATION = 0.35
SHRINK_WEIGHT = 1_000_000.0


def load_prior() -> dict[str, dict[str, float]]:
    rows = {}
    with open(PRIOR, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows[normalize_province(row["key"])] = {
                "valid_votes": float(row["valid_votes"]),
                **{party: float(row[name]) for party, name in PARTY_MAP.items()},
            }
    return rows


def load_result() -> dict[str, dict[str, float]]:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    return {
        normalize_province(row["name"]): {
            "valid_votes": float(row["valid_votes"]),
            **{party: float(row["shares"].get(party, 0.0)) for party in PARTY_MAP},
        }
        for row in payload["provinces"]
    }


def weighted_national(rows: dict[str, dict[str, float]], field: str) -> dict[str, float]:
    total = sum(row["valid_votes"] for row in rows.values())
    return {
        party: sum(row[party] * row["valid_votes"] for row in rows.values()) / total
        for party in PARTY_MAP
    }


def build() -> dict:
    prior = load_prior()
    result = load_result()
    national_prior = weighted_national(prior, "prior")
    national_result = weighted_national(result, "result")
    provinces = {}
    for key, row in result.items():
        old = prior.get(key)
        if not old:
            continue
        reliability = row["valid_votes"] / (row["valid_votes"] + SHRINK_WEIGHT)
        local = {}
        for party in PARTY_MAP:
            old_share = old.get(party, 0.0)
            new_share = row.get(party, 0.0)
            if old_share <= 0 or new_share <= 0:
                continue
            national_log = math.log(national_result[party] / national_prior[party])
            if abs(national_log) < 1e-6:
                continue
            province_log = math.log(new_share / old_share)
            deviation = (province_log - national_log) * reliability
            local[party] = round(
                max(-MAX_LOG_DEVIATION, min(MAX_LOG_DEVIATION, deviation)), 6
            )
        provinces[key] = local
    return {
        "meta": {
            "method": "province 2018->2023 log swing minus national swing, shrunk by electorate and clipped",
            "reference": "2018 province party shares -> 2023 province shares",
            "max_log_deviation": MAX_LOG_DEVIATION,
            "shrink_weight": SHRINK_WEIGHT,
            "note": "Province proxy for districts; split districts inherit their province until district history exists.",
        },
        "provinces": provinces,
    }


def main() -> None:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(payload['provinces'])} provinces)")


if __name__ == "__main__":
    main()
