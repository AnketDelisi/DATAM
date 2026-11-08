"""Scrape 2018 province-level party vote shares.

Source: Turkish Wikipedia 2018 general election province table (YSK-derived).
Output: ``data/2018_party_shares.csv``.

    python pipeline/scrape_2018_parties.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from pipeline.demographic_correlation import normalize_province
from pipeline.scrape_kurdish_support import fetch, read_tables, result_table, to_int

ROOT = Path(__file__).resolve().parent.parent
ACTUALS = ROOT / "data" / "actuals_2023.csv"
OUT = ROOT / "data" / "2018_party_shares.csv"
URL = "https://tr.wikipedia.org/wiki/2018_T%C3%BCrkiye_genel_se%C3%A7imleri"

PROVINCE_COL = 0
VALID_COL = 2
PARTY_COLS = {
    "AKP": 3,
    "CHP": 6,
    "MHP": 9,
    "HDP_DEM": 12,
    "IYI": 15,
    "OTHER": 18,
}


def build_frame() -> pd.DataFrame:
    actuals = pd.read_csv(ACTUALS)
    actuals["key"] = actuals["province"].map(normalize_province)
    province_by_key = dict(zip(actuals["key"], actuals["province"]))
    keys = set(province_by_key)
    table = result_table(read_tables(fetch(URL)))

    rows = {}
    for _, row in table.iterrows():
        province_text = re.sub(r"\s*\((?:I|II|III|IV|V)\)\s*$", "", str(row.iloc[PROVINCE_COL]))
        key = normalize_province(province_text)
        if key not in keys:
            continue
        valid = to_int(row.iloc[VALID_COL])
        votes = {party: to_int(row.iloc[column]) or 0 for party, column in PARTY_COLS.items()}
        total = sum(votes.values())
        if not valid or total <= 0:
            continue
        rows[key] = {
            "key": key,
            "province": province_by_key[key],
            "valid_votes": valid,
            **{party: votes[party] / total for party in PARTY_COLS},
        }

    missing = keys - set(rows)
    if missing:
        raise SystemExit(f"missing 2018 provinces: {sorted(missing)}")

    frame = pd.DataFrame(rows.values()).sort_values("key").reset_index(drop=True)
    share_columns = list(PARTY_COLS)
    totals = frame[share_columns].sum(axis=1)
    if ((totals - 1).abs() > 1e-9).any():
        raise SystemExit("2018 party shares do not sum to 1")
    return frame


def main() -> None:
    frame = build_frame()
    frame.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(frame)} provinces)")


if __name__ == "__main__":
    main()
