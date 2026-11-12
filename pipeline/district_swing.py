"""Estimate shrunk district-level swing deviations from 2018 to 2023.

Requires ``data/processed/parliament_2018_districts.csv`` from
``build_2018_districts.py``. Values are log deviations from the national
swing, shrunk by electorate and clipped; the 2028 scenario applies them to
each district's 2023 baseline.

    python pipeline/district_swing.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIOR = ROOT / "data" / "processed" / "parliament_2018_districts.csv"
RESULT = ROOT / "web" / "data" / "parliament_2023.json"
OUT = ROOT / "web" / "data" / "district_swing.json"

PARTIES = ["P9", "P21", "P11", "P22", "P12"]
MAX_LOG_DEVIATION = 0.35
SHRINK_WEIGHT = 100_000.0


def shares(row: dict, votes: dict) -> dict[str, float]:
    values = {party: float(votes.get(party, 0)) for party in PARTIES}
    total = float(row["valid_votes"])
    values["OTHER"] = max(0.0, total - sum(values.values()))
    denominator = sum(values.values())
    return {party: value / denominator for party, value in values.items() if value > 0}


def build() -> dict:
    with open(PRIOR, encoding="utf-8") as handle:
        prior = list(csv.DictReader(handle))
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    current = {row["id"]: row for row in payload["districts"]}
    prior_shares = {
        row["district_id"]: shares(
            row, {party: row.get(party, 0) for party in PARTIES}
        )
        for row in prior
    }

    total_prior = sum(float(row["valid_votes"]) for row in prior)
    total_current = sum(float(row["valid_votes"]) for row in payload["districts"])
    national_prior = {
        party: sum(float(row[party]) for row in prior) / total_prior
        for party in PARTIES
    }
    national_current = {
        party: sum(float(row["votes"].get(party, 0)) for row in payload["districts"])
        / total_current
        for party in PARTIES
    }

    districts = {}
    for district_id, row in current.items():
        old = prior_shares.get(district_id)
        if not old:
            continue
        new = shares(row, row["votes"])
        reliability = float(row["valid_votes"]) / (
            float(row["valid_votes"]) + SHRINK_WEIGHT
        )
        local = {}
        for party in PARTIES:
            old_share = old.get(party, 0.0)
            new_share = new.get(party, 0.0)
            if (
                old_share <= 0
                or new_share <= 0
                or national_prior[party] <= 0
                or national_current[party] <= 0
            ):
                continue
            deviation = (
                math.log(new_share / old_share)
                - math.log(national_current[party] / national_prior[party])
            ) * reliability
            local[party] = round(
                max(-MAX_LOG_DEVIATION, min(MAX_LOG_DEVIATION, deviation)), 6
            )
        districts[district_id] = local

    return {
        "meta": {
            "method": "district 2018->2023 log swing minus national swing, shrunk by electorate and clipped",
            "reference": "2018 district votes -> 2023 district votes",
            "max_log_deviation": MAX_LOG_DEVIATION,
            "shrink_weight": SHRINK_WEIGHT,
            "source": "YSK 2018 ballot-box transcription aggregated to 87 districts",
        },
        "districts": districts,
    }


def main() -> None:
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(payload['districts'])} districts)")


if __name__ == "__main__":
    main()
