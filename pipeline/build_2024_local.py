"""Build complete 2024 local-election actuals from the YSK data package.

Run with Python 3.13 because the ``ysk`` package requires it:

    uv run --no-project --python 3.13 --with ysk --with pyyaml \
        python pipeline/build_2024_local.py

Output: ``data/2024_local_actuals.csv`` with all 81 city mayors and 973
district mayors. City rows use the metropolitan mayor where one exists and the
central-district mayor otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import ysk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.demographic_correlation import normalize_province
ACTUALS = ROOT / "data" / "actuals_2023.csv"
OUT = ROOT / "data" / "2024_local_actuals.csv"

PARTY_COLUMNS = {
    "chp": "CHP",
    "ak_parti": "AKP",
    "mhp": "MHP",
    "iyi_parti": "IYI",
    "dem_parti": "HDP_DEM",
    "yeniden_refah": "YRP",
    "zafer_partisi": "ZP",
    "saadet": "SP",
    "buyuk_birlik": "BBP",
    "tip": "TIP",
}


def shares(row) -> dict[str, float]:
    valid = float(row["gecerli"])
    values = {
        party: float(row.get(column, 0) or 0) / valid if valid else 0.0
        for column, party in PARTY_COLUMNS.items()
    }
    values["OTHER"] = max(0.0, 1.0 - sum(values.values()))
    return values


def build_frame() -> pd.DataFrame:
    actuals = pd.read_csv(ACTUALS)
    actuals["key"] = actuals["province"].map(normalize_province)
    province_by_key = dict(zip(actuals["key"], actuals["province"]))
    province_keys = set(province_by_key)

    metro = ysk.election_results(
        ysk.Secim.YEREL_2024,
        ysk.Makam.BUYUKSEHIR_BELEDIYE_BASKANI,
        level="il",
    )
    city = ysk.election_results(
        ysk.Secim.YEREL_2024,
        ysk.Makam.BELEDIYE_BASKANI,
        level="ilce",
    )
    metro_keys = {normalize_province(province) for province in metro.index}
    non_metro = province_keys - metro_keys

    rows = []
    for province in metro.index:
        key = normalize_province(province)
        row = metro.loc[province]
        rows.append({
            "race": "metropolitan_mayor",
            "scope_type": "city",
            "key": key,
            "province_key": key,
            "province": province_by_key[key],
            "district": "",
            "total_votes": int(row["gecerli"]),
            **shares(row),
        })

    for key in sorted(non_metro):
        province = next(
            name for name in city.index.get_level_values(0)
            if normalize_province(name) == key
        )
        district = next(
            name for name in city.loc[province].index
            if normalize_province(name) == "MERKEZ"
        )
        row = city.loc[(province, district)]
        rows.append({
            "race": "metropolitan_mayor",
            "scope_type": "city",
            "key": key,
            "province_key": key,
            "province": province_by_key[key],
            "district": "",
            "total_votes": int(row["gecerli"]),
            **shares(row),
        })

    for (province, district), row in city.iterrows():
        province_key = normalize_province(province)
        district_key = normalize_province(district)
        rows.append({
            "race": "district_mayor",
            "scope_type": "district",
            "key": f"{province_key}/{district_key}",
            "province_key": province_key,
            "province": province_by_key.get(province_key, province),
            "district": district,
            "total_votes": int(row["gecerli"]),
            **shares(row),
        })

    frame = pd.DataFrame(rows).sort_values(["race", "key"]).reset_index(drop=True)
    share_columns = [*PARTY_COLUMNS.values(), "OTHER"]
    if ((frame[share_columns].sum(axis=1) - 1).abs() > 1e-9).any():
        raise SystemExit("2024 local shares do not sum to 1")
    expected_cities = len(province_keys)
    actual_cities = len(frame[frame["race"] == "metropolitan_mayor"])
    if actual_cities != expected_cities:
        raise SystemExit(f"expected {expected_cities} city rows, got {actual_cities}")
    return frame


def main() -> None:
    frame = build_frame()
    frame.to_csv(OUT, index=False)
    counts = frame["scope_type"].value_counts().to_dict()
    print(f"wrote {OUT.relative_to(ROOT)} ({counts})")


if __name__ == "__main__":
    main()
