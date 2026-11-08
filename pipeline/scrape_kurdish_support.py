"""Build the HDP/YSP political-support index (2015-2023).

This is a political-support index, not a Kurdish population estimate.

    python pipeline/scrape_kurdish_support.py

Sources: Turkish Wikipedia province-level general-election result tables,
YSK-derived. Outputs:
  data/analysis/kurdish_support.csv
  data/analysis/kurdish_support.md
  web/data/kurdish_support.json
"""

from __future__ import annotations

import io
import json
import re
import urllib.request
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pipeline.demographic_correlation import normalize_province

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "analysis"
WEB_OUT = ROOT / "web" / "data" / "kurdish_support.json"
REGIONS = ROOT / "config" / "regions.yaml"
ACTUALS = ROOT / "data" / "actuals_2023.csv"
PARLIAMENT = ROOT / "web" / "data" / "parliament_2023.json"

ELECTIONS = [
    ("2015-06", "Haziran 2015", "https://tr.wikipedia.org/wiki/Haziran_2015_T%C3%BCrkiye_genel_se%C3%A7imleri", 12, 11, 17),
    ("2015-11", "Kas\u0131m 2015", "https://tr.wikipedia.org/wiki/Kas%C4%B1m_2015_T%C3%BCrkiye_genel_se%C3%A7imleri", 13, 12, 2),
    ("2018", "2018", "https://tr.wikipedia.org/wiki/2018_T%C3%BCrkiye_genel_se%C3%A7imleri", 13, 12, 2),
    ("2023", "2023", "https://tr.wikipedia.org/wiki/2023_T%C3%BCrkiye_genel_se%C3%A7imleri", 16, 15, 2),
]


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def read_tables(html: str) -> list[pd.DataFrame]:
    return pd.read_html(io.StringIO(html), header=None, decimal=",", thousands=None)


def result_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    candidates = []
    for table in tables:
        if table.shape[0] < 70 or table.shape[1] < 12:
            continue
        header = " ".join(str(value) for value in table.columns)
        if "Seçim" in header and ("HDP" in header or "YSP" in header):
            candidates.append(table)
    if not candidates:
        raise SystemExit("province result table not found")
    return max(candidates, key=lambda table: table.shape[0])


def to_int(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    text = text.replace("%", "").replace(" ", "").replace(".", "").replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def to_num(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    text = text.replace("%", "").replace(" ", "")
    if text in {"", "-", "–", "—"}:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def to_share(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    text = text.replace("%", "").replace(" ", "")
    if text in {"", "-", "–", "—"}:
        return None
    try:
        return float(text.replace(",", ".")) / 100
    except ValueError:
        return None


def load_regions() -> dict[str, str]:
    payload = yaml.safe_load(REGIONS.read_text(encoding="utf-8"))
    return {
        province: region
        for region, provinces in payload["regions"].items()
        for province in provinces
    }


def build_index() -> tuple[pd.DataFrame, dict]:
    actuals = pd.read_csv(ACTUALS)
    actuals["key"] = actuals["province"].map(normalize_province)
    province_by_key = dict(zip(actuals["key"], actuals["province"]))
    keys = set(province_by_key)
    columns = {}
    for election_id, label, url, share_col, vote_col, valid_col in ELECTIONS:
        table = result_table(read_tables(fetch(url)))
        totals = {}
        shares = {}
        for _, row in table.iterrows():
            province_text = re.sub(r"\s*\((?:I|II|III|IV|V)\)\s*$", "", str(row.iloc[0]))
            key = normalize_province(province_text)
            if key not in keys:
                continue
            votes = to_int(row.iloc[vote_col])
            valid = to_int(row.iloc[valid_col])
            share = to_share(row.iloc[share_col])
            if votes is not None and valid:
                previous = totals.get(key, (0.0, 0.0))
                totals[key] = (previous[0] + votes, previous[1] + valid)
            if share is not None:
                shares[key] = share
        parsed = {}
        for key in keys:
            if key in totals and totals[key][1] > 0:
                parsed[key] = totals[key][0] / totals[key][1]
            elif key in shares:
                parsed[key] = shares[key]
        missing = keys - set(parsed)
        if missing:
            raise SystemExit(f"{label}: missing {sorted(missing)}")
        columns[election_id] = parsed
        print(f"{label}: {len(parsed)} provinces, mean {np.mean(list(parsed.values())):.1%}")

    frame = pd.DataFrame(columns).sort_index()
    frame.index.name = "key"
    frame = frame.reset_index()
    frame["province"] = frame["key"].map(province_by_key)
    frame["region"] = frame["key"].map(load_regions())
    frame["index"] = frame[list(columns)].mean(axis=1)
    frame["index_z"] = (
        (frame["index"] - frame["index"].mean()) / frame["index"].std()
    )
    frame["percentile"] = frame["index"].rank(pct=True) * 100
    frame["change_2015_2023"] = frame["2023"] - frame["2015-06"]

    stability = {}
    for left, right in combinations(list(columns), 2):
        stability[f"{left}__{right}"] = {
            "pearson": float(frame[left].corr(frame[right])),
            "spearman": float(frame[left].rank().corr(frame[right].rank())),
        }

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "unweighted mean of HDP/YSP valid-vote shares in four general elections",
        "elections": [{"id": e, "label": label, "source": url} for e, label, url, *_ in ELECTIONS],
        "note": "political-support index, not a Kurdish population estimate",
        "stability": stability,
        "top_provinces": frame.nlargest(10, "index")[
            ["province", "index", "percentile"]
        ].to_dict(orient="records"),
        "bottom_provinces": frame.nsmallest(10, "index")[
            ["province", "index", "percentile"]
        ].to_dict(orient="records"),
    }
    return frame, meta


def build_ilce_index(frame: pd.DataFrame) -> pd.DataFrame:
    payload = json.loads(PARLIAMENT.read_text(encoding="utf-8"))
    province_index = dict(zip(frame["key"], frame["index"]))
    province_hdp = {
        province["geo_key"]: province["shares"].get("P12", 0)
        for province in payload["provinces"]
    }
    rows = []
    for ilce in payload["ilce"]:
        key = ilce["province_key"]
        valid = ilce.get("valid_votes") or 0
        hdp = (ilce.get("votes") or {}).get("P12", 0) / valid if valid else 0
        base = province_index.get(key)
        province_share = province_hdp.get(key, 0)
        index = base * (hdp / province_share) if base is not None and province_share > 0 else base
        rows.append({
            "geo_id": ilce["geo_id"],
            "name": ilce.get("geo_name") or ilce["name"],
            "province": ilce.get("province"),
            "province_key": key,
            "hdp_2023": hdp,
            "province_index": base,
            "index": max(0.0, min(1.0, index or 0.0)),
        })
    return pd.DataFrame(rows).sort_values(["province", "name"]).reset_index(drop=True)


def write_outputs(frame: pd.DataFrame, meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "kurdish_support.csv", index=False)
    ilce = build_ilce_index(frame)
    ilce.to_csv(OUT / "kurdish_support_ilce.csv", index=False)
    meta["ilce_note"] = (
        "il?e index is an approximation: province index scaled by 2023 HDP/DEM "
        "il?e vote share; not used in seat allocation"
    )
    payload = {
        "meta": meta,
        "provinces": frame[
            ["key", "province", "region", "2015-06", "2015-11", "2018", "2023", "index", "index_z", "percentile", "change_2015_2023"]
        ].to_dict(orient="records"),
        "ilce": ilce.to_dict(orient="records"),
    }
    WEB_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# HDP/YSP siyasi destek göstergesi",
        "",
        "2015 Haziran, 2015 Kasım, 2018 ve 2023 genel seçimlerindeki il bazlı",
        "HDP/YSP geçerli oy oranlarının eşit ağırlıklı ortalamasıdır.",
        "",
        "**Bu bir Kürt nüfus tahmini değildir.** HDP/YSP oyu Kürt seçmenin",
        "tamamını temsil etmez; partinin aldığı oyların bir kısmı Kürt olmayan",
        "seçmenden gelir ve Kürt seçmenin bir kısmı başka partilere oy verir.",
        "",
        "## En yüksek 10 il",
        "",
        "| İl | Gösterge | Yüzdelik |",
        "|---|---:|---:|",
    ]
    for row in meta["top_provinces"]:
        lines.append(
            f"| {row['province']} | {row['index']:.3f} | {row['percentile']:.0f} |"
        )
    lines += ["", "## Seçimler arası sıra korelasyonu", "", "| Çift | Pearson | Spearman |", "|---|---:|---:|"]
    for key, value in meta["stability"].items():
        lines.append(
            f"| {key.replace('__', ' vs ')} | {value['pearson']:.3f} | "
            f"{value['spearman']:.3f} |"
        )
    lines += ["", "Kaynak: Türkçe Wikipedia il sonuç tabloları (YSK verisi)."]
    (OUT / "kurdish_support.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    frame, meta = build_index()
    write_outputs(frame, meta)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(frame)} provinces)")
    print(meta["top_provinces"][:5])


if __name__ == "__main__":
    main()
