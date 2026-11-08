"""Backtest house effects on all 2024 local-election polls.

Trains on 2015–2023 polls only and scores each city and district separately.
Output: ``data/analysis/house_effects_2024.md``.

    python pipeline/backtest_2024_local.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.demographic_correlation import normalize_province
from pipeline.house_effects import (
    Model,
    aggregate,
    apply_poll_effects,
    fit_hierarchical_one_level,
    fit_one_level,
    load_polls,
    load_yaml,
)

ROOT = Path(__file__).resolve().parent.parent
ACTUALS = ROOT / "data" / "2024_local_actuals.csv"
OUT = ROOT / "data" / "analysis" / "house_effects_2024.md"
CUTOFF = "2024-03-31"
META = {"race", "scope_type", "key", "province_key", "province", "district", "total_votes"}


def scope_key(scope: str) -> str:
    parts = str(scope).split("/")
    return "/".join(normalize_province(part) for part in parts)


def load_actuals() -> tuple[dict[tuple[str, str], dict[str, float]], dict[tuple[str, str], str]]:
    frame = pd.read_csv(ACTUALS)
    parties = [column for column in frame.columns if column not in META]
    actuals = {}
    scope_types = {}
    for _, row in frame.iterrows():
        key = (row["race"], row["key"])
        actuals[key] = {party: float(row[party]) for party in parties}
        scope_types[key] = row["scope_type"]
    return actuals, scope_types


def group_polls(polls: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped = {}
    for poll in polls:
        if poll["election_id"] != "2024-local":
            continue
        key = (poll["race"], scope_key(poll["scope"]))
        grouped.setdefault(key, []).append(poll)
    return grouped


def summarize(rows: list[dict]) -> dict:
    errors = [error for row in rows for error in row["errors"]]
    return {
        "scopes": len(rows),
        "cells": len(errors),
        "mae": sum(errors) / len(errors) if errors else None,
        "winner_accuracy": (
            sum(row["correct"] for row in rows) / len(rows) if rows else None
        ),
    }


def score(effects, grouped, actuals, scope_types, one_level: bool, bloc_of=None) -> dict:
    rows = []
    for key, actual in actuals.items():
        polls = grouped.get(key, [])
        if not polls:
            continue
        adjusted = [
            apply_poll_effects(poll, effects, bloc_of or {}, one_level=one_level)
            for poll in polls
        ]
        result = aggregate(adjusted, list(actual), cutoff=CUTOFF)
        errors = [abs(result.get(party, 0.0) - share) for party, share in actual.items()]
        winner = max(result, key=result.get) if result else None
        actual_winner = max(actual, key=actual.get)
        rows.append({
            "scope_type": scope_types[key],
            "errors": errors,
            "correct": int(winner == actual_winner),
        })
    return {
        "all": summarize(rows),
        "city": summarize([row for row in rows if row["scope_type"] == "city"]),
        "district": summarize([row for row in rows if row["scope_type"] == "district"]),
    }


def metric_rows(label: str, values: dict) -> list[str]:
    return [
        f"| {label} | {values['all']['mae']:.5f} | {values['all']['winner_accuracy']:.1%} "
        f"| {values['city']['mae']:.5f} | {values['district']['mae']:.5f} |"
    ]


def main() -> None:
    polls = load_polls()
    actuals, scope_types = load_actuals()
    grouped = group_polls(polls)
    train = [poll for poll in polls if poll["election_id"] != "2024-local"]
    model = Model(train, load_yaml("entities.yaml"), load_yaml("house_effects.yaml"),
                  date.fromisoformat(CUTOFF))
    two_level = model.fit()
    one_level = fit_one_level(model)
    hierarchical = fit_hierarchical_one_level(model)

    raw = score({}, grouped, actuals, scope_types, one_level=False)
    one = score(one_level, grouped, actuals, scope_types, one_level=True)
    hier = score(hierarchical, grouped, actuals, scope_types, one_level=True)
    two = score(two_level, grouped, actuals, scope_types, one_level=False,
                bloc_of=model.bloc_of)

    lines = [
        "# 2024 local-election house-effect backtest",
        "",
        "Pollster effects are trained on 2015–2023 polls only. Each city and",
        "district is aggregated separately and compared with the 31 March 2024",
        "result. The sample covers every 2024 local poll with a matching actual:",
        f"{raw['all']['scopes']} scopes ({raw['city']['scopes']} city, "
        f"{raw['district']['scopes']} district).",
        "",
        "| model | all MAE | winner accuracy | city MAE | district MAE |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, values in [
        ("raw average", raw),
        ("two-level", two),
        ("one-level", one),
        ("hierarchical one-level", hier),
    ]:
        lines.extend(metric_rows(label, values))
    lines += [
        "",
        "One-level effects give the best winner accuracy and are effectively tied",
        "with two-level on district MAE; the production local mode stays one-level.",
        "The 2024 result is used only for this diagnostic; it is not part of the",
        "production house-effect training data.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for label, values in [("raw", raw), ("two", two), ("one", one), ("hier", hier)]:
        print(label, {
            scope: {
                "scopes": values[scope]["scopes"],
                "mae": round(values[scope]["mae"], 5),
                "winner_accuracy": round(values[scope]["winner_accuracy"], 4),
            }
            for scope in ("all", "city", "district")
        })


if __name__ == "__main__":
    main()
