"""Fetch 2023 presidential first-round and runoff results by province.

    uv run python pipeline/fetch_president.py
    uv run python pipeline/fetch_president.py --limit 3
    uv run python pipeline/fetch_president.py --refresh

Writes data/processed/president_2023.csv. Raw responses are cached under
data/raw/ysk/2023_president/.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://acikveri.ysk.gov.tr/api/"
SECIM_TURU = 9  # Cumhurbaskanligi
FIRST = 20230
RUNOFF = 20240
RAW = Path("data/raw/ysk/2023_president")
PROCESSED = Path("data/processed")
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(endpoint: str, **params):
    query = urllib.parse.urlencode(
        {key: "" if value is None else value for key, value in params.items()}
    )
    url = f"{API}{endpoint}?{query}"
    last: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - retry public API
            last = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"YSK request failed: {url}") from last


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


def load_or_fetch(path: Path, endpoint: str, refresh: bool, **params):
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = get(endpoint, **params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    time.sleep(0.15)
    return data


def fetch_election(secim_id: int, refresh: bool, limit: int = 0):
    provinces = get("getIlList", secimId=secim_id, secimTuru=SECIM_TURU)
    if limit:
        provinces = provinces[:limit]

    header_data = get(
        "getIttifakSecimSonucBaslikList",
        secimId=secim_id,
        secimCevresiId=provinces[0]["secim_CEVRESI_ID"],
        ilId=provinces[0]["il_ID"],
        bagimsiz=1,
    )
    candidates = {}
    for header in header_data:
        column = header["column_NAME"]
        if not column.startswith("bagimsiz"):
            continue
        if "ALDIGI_OY" not in column or column == "bagimsiz_ALDIGI_OY":
            continue
        candidates[int(header["sira_NO"])] = {
            "name": header["ad"],
            "column": column,
        }

    results = []
    for i, province in enumerate(provinces, 1):
        params = {
            "secimId": secim_id,
            "secimTuru": SECIM_TURU,
            "ilId": province["il_ID"],
            "ilceId": "",
            "beldeId": "",
            "birimId": "",
            "muhtarlikId": "",
            "cezaeviId": "",
            "sandikTuru": "",
            "sandikNoIlk": "",
            "sandikNoSon": "",
            "ulkeId": "",
            "disTemsilcilikId": "",
            "gumrukId": "",
            "yurtIciDisi": 1,
            "sandikRumuzIlk": "",
            "sandikRumuzSon": "",
            "secimCevresiId": province["secim_CEVRESI_ID"],
            "sandikId": "",
            "sorguTuru": "",
        }
        rows = load_or_fetch(
            RAW / f"{secim_id}_{province['il_ID']}.json",
            "getSecimSandikSonucList",
            refresh,
            **params,
        )
        votes = {sira: 0 for sira in candidates}
        valid = ballots = electorate = 0
        for row in rows:
            valid += int(row.get("gecerli_OY_TOPLAMI") or 0)
            ballots += int(row.get("oy_KULLANAN_SECMEN_SAYISI") or 0)
            electorate += int(row.get("secmen_SAYISI") or 0)
            for sira, candidate in candidates.items():
                votes[sira] += int(row.get(candidate["column"]) or 0)
        results.append(
            {
                "il_id": province["il_ID"],
                "province": province["il_ADI"],
                "votes": votes,
                "valid": valid,
                "ballots": ballots,
                "electorate": electorate,
            }
        )
        print(
            f"[{secim_id}] [{i}/{len(provinces)}] {province['il_ADI']}: "
            f"{len(rows)} ilce, {valid:,} valid"
        )

    return candidates, results


def find_candidate(candidates: dict, needle: str) -> int:
    key = norm(needle)
    normalized = [(sira, norm(candidate["name"])) for sira, candidate in candidates.items()]
    for sira, name in normalized:
        if name == key or name.endswith(" " + key) or name.startswith(key):
            return sira
    for sira, name in normalized:
        if key in name:
            return sira
    raise KeyError(f"candidate not found: {needle}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    first_candidates, first = fetch_election(FIRST, args.refresh, args.limit)
    runoff_candidates, runoff = fetch_election(RUNOFF, args.refresh, args.limit)

    a1 = find_candidate(first_candidates, "ERDO")
    b1 = find_candidate(first_candidates, "KILIÇ")
    c1 = find_candidate(first_candidates, "OĞAN")
    d1 = find_candidate(first_candidates, "İNCE")
    a2 = find_candidate(runoff_candidates, "ERDO")
    b2 = find_candidate(runoff_candidates, "KILIÇ")

    first_by_id = {row["il_id"]: row for row in first}
    runoff_by_id = {row["il_id"]: row for row in runoff}

    rows = []
    for il_id in sorted(first_by_id):
        f = first_by_id[il_id]
        r = runoff_by_id.get(il_id)
        if r is None:
            raise SystemExit(f"missing runoff for il_id={il_id}")
        rows.append(
            {
                "il_id": il_id,
                "province": f["province"],
                "first_A": f["votes"][a1],
                "first_B": f["votes"][b1],
                "first_C": f["votes"][c1],
                "first_D": f["votes"][d1],
                "first_valid": f["valid"],
                "first_ballots": f["ballots"],
                "first_electorate": f["electorate"],
                "runoff_A": r["votes"][a2],
                "runoff_B": r["votes"][b2],
                "runoff_valid": r["valid"],
                "runoff_ballots": r["ballots"],
                "runoff_electorate": r["electorate"],
            }
        )

    df = pd.DataFrame(rows)
    for prefix in ("first", "runoff"):
        cols = [c for c in df.columns if c.startswith(f"{prefix}_") and c not in
                (f"{prefix}_valid", f"{prefix}_ballots", f"{prefix}_electorate")]
        diff = (df[cols].sum(axis=1) - df[f"{prefix}_valid"]).abs()
        if diff.max() > 0:
            print(f"WARN {prefix} candidate sum differs from valid votes: max {diff.max()}")

    df.to_csv(PROCESSED / "president_2023.csv", index=False)

    total_valid = int(df["first_valid"].sum())
    print("\nfirst round:")
    for col in ("first_A", "first_B", "first_C", "first_D"):
        print(f"  {col}: {df[col].sum()/total_valid:6.2%}")
    runoff_valid = int(df["runoff_valid"].sum())
    print("runoff:")
    for col in ("runoff_A", "runoff_B"):
        print(f"  {col}: {df[col].sum()/runoff_valid:6.2%}")
    print(f"\nwrote {PROCESSED/'president_2023.csv'} ({len(df)} provinces)")


if __name__ == "__main__":
    main()
