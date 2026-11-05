"""Project 2028 district seats from 2023 electorates and growth assumptions.

    python pipeline/project_2028_seats.py

The projection preserves the 2023 seat map when all districts grow at the same
rate. Province-specific growth overrides can shift seats. It is an
apportionment scenario, not an official 2028 map.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pipeline.demographic_correlation import normalize_province

ROOT = Path(__file__).resolve().parent.parent
DISTRICTS = ROOT / "data" / "processed" / "parliament_2023_districts.csv"
CONFIG = ROOT / "config" / "2028_seats.yaml"
OUT = ROOT / "web" / "data" / "seat_projection_2028.json"


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def project_seats(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    years = int(cfg["target_year"]) - int(cfg["base_year"])
    national = float(cfg.get("national_annual_growth", 0.0))
    overrides = cfg.get("province_annual_growth") or {}
    total_seats = int(cfg["total_seats"])

    rows = []
    for _, row in frame.iterrows():
        province_key = normalize_province(str(row["province"]).split("-")[0])
        growth = float(overrides.get(province_key, national))
        projected = float(row["electorate"]) * (1 + growth) ** years
        rows.append({
            "district_id": row["district_id"],
            "province": row["province"],
            "province_key": province_key,
            "base_seats": int(row["seats"]),
            "base_electorate": int(row["electorate"]),
            "projected_electorate": projected,
            "growth": growth,
        })

    projected = pd.DataFrame(rows)
    weights = (
        projected["base_seats"]
        * projected["projected_electorate"]
        / projected["base_electorate"]
    )
    quota = weights / weights.sum() * total_seats
    floor = np.floor(quota.to_numpy()).astype(int)
    seats = pd.Series(np.clip(floor, 1, None), index=quota.index)
    remaining = total_seats - int(seats.sum())
    order = (quota - floor).sort_values(ascending=False).index
    for index in order:
        if remaining <= 0:
            break
        seats.loc[index] += 1
        remaining -= 1
    projected["seats"] = seats
    return projected


def main() -> None:
    cfg = load_config()
    frame = pd.read_csv(DISTRICTS)
    projected = project_seats(frame, cfg)
    if int(projected["seats"].sum()) != int(cfg["total_seats"]):
        raise SystemExit("seat total does not match config")

    payload = {
        "meta": {
            "base_year": cfg["base_year"],
            "target_year": cfg["target_year"],
            "total_seats": cfg["total_seats"],
            "national_annual_growth": cfg.get("national_annual_growth", 0),
            "method": "2023 seats weighted by projected electorate growth, largest remainder",
            "note": "scenario apportionment, not an official 2028 map",
        },
        "districts": {
            row["district_id"]: int(row["seats"])
            for _, row in projected.iterrows()
        },
        "provinces": {
            province: int(group["seats"].sum())
            for province, group in projected.groupby("province_key")
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({int(projected['seats'].sum())} seats)")


if __name__ == "__main__":
    main()
