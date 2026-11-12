"""Aggregate 2018 parliamentary ballot-box results to 87 electoral districts.

Source CSV:
https://github.com/oztalha/YSK-2018/blob/master/YSK-MVCB-18.csv

The repository is a public transcription of YSK's 24 June 2018 ballot-box
results.  Keep the raw CSV outside git; the processed district aggregate is
committed.

    python pipeline/build_2018_districts.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.demographic_correlation import normalize_province

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ysk" / "2018_general_mv.csv"
DISTRICTS = ROOT / "web" / "data" / "parliament_2023.json"
OUT = ROOT / "data" / "processed" / "parliament_2018_districts.csv"

# Column positions are stable in the source CSV; avoid Turkish header literals
# so the script remains readable on every console encoding.
PARTY_COLUMNS = {"P9": 10, "P11": 11, "P12": 14, "P21": 15, "P22": 17}


def build() -> pd.DataFrame:
    if not RAW.exists():
        raise SystemExit(
            f"missing {RAW}; download YSK-MVCB-18.csv from the source URL above"
        )
    frame = pd.read_csv(RAW, encoding="utf-8-sig")
    columns = frame.columns.tolist()
    province_col, district_col = columns[0], columns[1]
    valid_col = columns[8]
    ballots_col = columns[5]
    electorate_col = columns[4]

    payload = json.loads(DISTRICTS.read_text(encoding="utf-8"))
    by_ilce = {
        (normalize_province(row["province"]), normalize_province(row["name"])): row
        for row in payload["ilce"]
    }
    by_district = {row["id"]: row for row in payload["districts"]}

    frame["_province"] = frame[province_col].map(normalize_province)
    frame["_ilce"] = frame[district_col].map(normalize_province)
    frame["_district"] = [
        by_ilce[(province, ilce)]["district_id"]
        for province, ilce in zip(frame["_province"], frame["_ilce"])
    ]

    rows = []
    for district_id, group in frame.groupby("_district"):
        meta = by_district[district_id]
        row = {
            "district_id": district_id,
            "province": meta["province"],
            "il_id": meta["il_id"],
            "secim_cevresi_id": meta["secim_cevresi_id"],
            "seats": meta["seats"],
            "valid_votes": int(group[valid_col].sum()),
            "ballots_cast": int(group[ballots_col].sum()),
            "electorate": int(group[electorate_col].sum()),
        }
        for party, position in PARTY_COLUMNS.items():
            row[party] = int(group[columns[position]].sum())
        row["OTHER"] = max(
            0, row["valid_votes"] - sum(row[party] for party in PARTY_COLUMNS)
        )
        rows.append(row)

    result = pd.DataFrame(rows).sort_values("district_id").reset_index(drop=True)
    if len(result) != 87:
        raise ValueError(f"expected 87 districts, got {len(result)}")
    if int(result["seats"].sum()) != 600:
        raise ValueError(f"expected 600 seats, got {int(result['seats'].sum())}")
    return result


def main() -> None:
    frame = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(frame)} districts, {frame.seats.sum()} seats)")


if __name__ == "__main__":
    main()
