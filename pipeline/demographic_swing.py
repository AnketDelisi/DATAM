"""Build province-level demographic tilt scores for projection scenarios.

The score is the standardized demographic component of an OLS model:

    outcome ~ standardized demographics + region FE + log(electorate)

It is not a causal effect. The simulator uses it only to vary a national swing
across provinces, with a user-controlled strength.

    python pipeline/demographic_swing.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.demographic_correlation import DEMOGRAPHICS, OUTCOMES

ROOT = Path(__file__).resolve().parent.parent
FRAME = ROOT / "data" / "analysis" / "province_demographics.csv"
OUT = ROOT / "web" / "data" / "demographic_swing.json"


def zscore(values: np.ndarray) -> np.ndarray:
    std = float(values.std())
    if std <= 1e-12:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def build_swing(frame: pd.DataFrame) -> dict:
    frame = frame.copy()
    frame["log_electorate"] = np.log(frame["electorate"].astype(float))
    demographics = frame[DEMOGRAPHICS].to_numpy(dtype=float)
    demographics = (demographics - demographics.mean(axis=0)) / demographics.std(axis=0)
    regions = pd.get_dummies(frame["region"], drop_first=True, dtype=float).to_numpy()
    controls = np.column_stack([
        np.ones(len(frame)),
        demographics,
        regions,
        frame["log_electorate"].to_numpy(dtype=float),
    ])

    provinces = {}
    for key in frame["key"]:
        provinces[key] = {}

    for outcome in OUTCOMES:
        y = frame[outcome].to_numpy(dtype=float)
        beta, _, _, _ = np.linalg.lstsq(controls, y, rcond=None)
        demographic_beta = beta[1:1 + len(DEMOGRAPHICS)]
        score = zscore(demographics @ demographic_beta)
        for key, value in zip(frame["key"], score):
            provinces[key][outcome] = round(float(value), 4)

    return {
        "meta": {
            "method": "standardized demographic component of OLS outcome ~ demographics + region FE + log(electorate)",
            "n": len(frame),
            "outcomes": OUTCOMES,
            "demographics": DEMOGRAPHICS,
            "note": "descriptive tilt for scenario redistribution, not a causal effect",
        },
        "provinces": provinces,
    }


def main() -> None:
    if not FRAME.exists():
        raise SystemExit("run pipeline/demographic_correlation.py first")
    payload = build_swing(pd.read_csv(FRAME))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({payload['meta']['n']} provinces)")


if __name__ == "__main__":
    main()
