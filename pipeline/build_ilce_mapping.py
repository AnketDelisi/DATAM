"""Match YSK ilce results to geoBoundaries ADM2 polygons.

    uv run --with shapely python pipeline/build_ilce_mapping.py

Outputs:
  data/processed/ilce_geo_mapping.csv
  web/geo/tr-ilce.geojson   (with province properties, rewound for d3-geo)

The ilce GeoJSON is from geoBoundaries ADM2 (ODbL 1.0). The script adds the
parent province via a point-in-polygon test, then matches YSK ilce names to
GeoJSON names within that province. Run once after replacing the source file.
"""

from __future__ import annotations

import json
import re
from difflib import get_close_matches
from pathlib import Path

import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_GEO = ROOT / "web" / "geo" / "tr-provinces.geojson"
ILCE_GEO = ROOT / "web" / "geo" / "tr-ilce.geojson"
PROCESSED = ROOT / "data" / "processed"
MAPPING = PROCESSED / "ilce_geo_mapping.csv"

# GeoBoundaries/OSM sometimes uses a different local name for the same
# district. Keys are (province_key, ysk_ilce_key); values are normalized
# GeoJSON shape names.
ALIASES = {
    ("CANAKKALE", "GOKCEADA"): "IMBROS",
    ("ISTANBUL", "ADALAR"): "PRINCE ISLANDS",
    ("KUTAHYA", "GEDIZ"): "GEDIZ MERKEZ",
}


def norm(value: str) -> str:
    return (
        str(value)
        .upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ç", "C")
        .replace("Ö", "O")
        .replace("Ü", "U")
        .replace("Â", "A")
        .strip()
    )


def strip_parenthetical(value: str) -> str:
    return norm(re.sub(r"\s*\([^)]*\)", "", str(value)))


def rewind(geojson: dict) -> dict:
    if geojson.get("_rewound"):
        return geojson
    for feature in geojson["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            geometry["coordinates"] = [ring[::-1] for ring in geometry["coordinates"]]
        elif geometry["type"] == "MultiPolygon":
            geometry["coordinates"] = [
                [ring[::-1] for ring in polygon] for polygon in geometry["coordinates"]
            ]
    geojson["_rewound"] = True
    return geojson


def main() -> None:
    provinces = json.loads(PROVINCE_GEO.read_text(encoding="utf-8"))
    ilce = json.loads(ILCE_GEO.read_text(encoding="utf-8"))

    province_shapes = [
        (
            feature["properties"]["shapeName"],
            norm(feature["properties"]["shapeName"]),
            shape(feature["geometry"]),
        )
        for feature in provinces["features"]
    ]

    for feature in ilce["features"]:
        geometry = shape(feature["geometry"])
        point = geometry.representative_point()
        hit = None
        for name, key, polygon in province_shapes:
            if polygon.contains(point):
                hit = (name, key)
                break
        if hit is None:
            name, key, _ = min(province_shapes, key=lambda item: item[2].distance(point))
            hit = (name, key)
        feature["properties"]["province"] = hit[0]
        feature["properties"]["province_key"] = hit[1]

    districts = pd.read_csv(PROCESSED / "parliament_2023_districts.csv")
    districts = districts[["district_id", "province", "il_id"]].drop_duplicates()
    ysk = pd.read_csv(PROCESSED / "parliament_2023_ilce.csv")
    ysk = ysk.merge(districts, on="district_id", how="left")
    ysk["province_base"] = ysk["province"].str.split("-").str[0]
    ysk = ysk[["il_id", "province_base", "ilce_id", "ilce"]].drop_duplicates()
    ysk = ysk.sort_values(["province_base", "ilce"]).reset_index(drop=True)

    used: set[str] = set()
    rows = []
    unmatched = []

    for _, record in ysk.iterrows():
        pkey = norm(record["province_base"])
        ikey = norm(record["ilce"])
        candidates = [
            feature
            for feature in ilce["features"]
            if feature["properties"]["province_key"] == pkey
            and feature["properties"]["shapeID"] not in used
        ]
        match = None
        match_type = None

        alias = ALIASES.get((pkey, ikey))
        if alias:
            aliased = [
                feature
                for feature in candidates
                if norm(feature["properties"]["shapeName"]) == alias
            ]
            if len(aliased) == 1:
                match = aliased[0]
                match_type = "alias"

        exact = [
            feature
            for feature in candidates
            if norm(feature["properties"]["shapeName"]) == ikey
        ]
        if match is None and exact:
            match = exact[0]
            match_type = "exact"

        if match is None:
            central = [
                feature
                for feature in candidates
                if "MERKEZ" in norm(feature["properties"]["shapeName"])
                or norm(feature["properties"]["shapeName"]) == pkey
            ]
            if ("MERKEZ" in ikey or ikey == pkey) and len(central) == 1:
                match = central[0]
                match_type = "merkez"

        if match is None:
            without_parens = [
                feature
                for feature in candidates
                if strip_parenthetical(feature["properties"]["shapeName"]) == ikey
            ]
            if len(without_parens) == 1:
                match = without_parens[0]
                match_type = "parenthetical"

        if match is None:
            names = [norm(feature["properties"]["shapeName"]) for feature in candidates]
            close = get_close_matches(ikey, names, n=1, cutoff=0.6)
            if close:
                match = next(
                    feature
                    for feature in candidates
                    if norm(feature["properties"]["shapeName"]) == close[0]
                )
                match_type = "fuzzy"

        if match is None:
            unmatched.append(
                (
                    record["province_base"],
                    record["ilce"],
                    [norm(feature["properties"]["shapeName"]) for feature in candidates],
                )
            )
            continue

        used.add(match["properties"]["shapeID"])
        rows.append(
            {
                "il_id": int(record["il_id"]),
                "province_base": record["province_base"],
                "ilce_id": int(record["ilce_id"]),
                "ilce": record["ilce"],
                "geo_shape_id": match["properties"]["shapeID"],
                "geo_shape_name": match["properties"]["shapeName"],
                "geo_province": match["properties"]["province"],
                "match_type": match_type,
            }
        )

    if unmatched:
        print(f"UNMATCHED {len(unmatched)}:")
        for province, name, candidates in unmatched:
            print(f"  {province} / {name} -> {candidates}")
        raise SystemExit("Resolve unmatched ilce names before continuing")

    if len(rows) != len(ysk) or len(used) != len(ysk):
        raise SystemExit(f"match count mismatch: rows={len(rows)} used={len(used)} ysk={len(ysk)}")

    if len(used) != len(ilce["features"]):
        raise SystemExit(
            f"not all GeoJSON features matched: used={len(used)} geo={len(ilce['features'])}"
        )

    ilce = rewind(ilce)
    ILCE_GEO.write_text(
        json.dumps(ilce, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_csv(MAPPING, index=False)
    print(
        f"matched {len(rows)} ilce -> {MAPPING.name}; "
        f"rewrote {ILCE_GEO.name} ({ILCE_GEO.stat().st_size/1024/1024:.1f} MB)"
    )


if __name__ == "__main__":
    main()
