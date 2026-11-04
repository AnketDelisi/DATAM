"""Fetch 2023 parliamentary results from the YSK open-data API.

    uv run python pipeline/fetch_ysk.py
    uv run python pipeline/fetch_ysk.py --limit 3      # smoke test
    uv run python pipeline/fetch_ysk.py --refresh      # ignore cache

The API returns one row per ilce for an electoral district. We sum those to
one row per electoral district, which is what D'Hondt needs. Raw JSON is cached
under data/raw/ysk/2023_parliament/.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://acikveri.ysk.gov.tr/api/"
SECIM_ID = 20230
SECIM_TURU = 8  # Milletvekilligi
ALLIANCE_NAMES = {
    1: "SOSYALIST GUC BIRLIGI ITTIFAKI",
    2: "CUMHUR ITTIFAKI",
    3: "EMEK VE OZGURLUK ITTIFAKI",
    4: "MILLET ITTIFAKI",
    5: "ATA ITTIFAKI",
}
RAW = Path("data/raw/ysk/2023_parliament")
PROCESSED = Path("data/processed")
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(endpoint: str, **params) -> object:
    query = urllib.parse.urlencode(
        {k: "" if v is None else v for k, v in params.items()}
    )
    url = f"{API}{endpoint}?{query}"
    last: Exception | None = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - network retries
            last = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"YSK request failed: {url}") from last


def norm(value: str) -> str:
    return (
        value.upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ç", "C")
        .replace("Ö", "O")
        .replace("Ü", "U")
        .replace("Â", "A")
        .strip()
    )


def load_or_fetch(path: Path, endpoint: str, refresh: bool, **params) -> object:
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = get(endpoint, **params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    time.sleep(0.15)
    return data


def district_params(district: dict, yurt_ici_disi: int = 1) -> dict:
    return {
        "secimId": SECIM_ID,
        "secimTuru": SECIM_TURU,
        "ilId": district["il_ID"],
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
        "yurtIciDisi": yurt_ici_disi,
        "sandikRumuzIlk": "",
        "sandikRumuzSon": "",
        "secimCevresiId": district["secim_CEVRESI_ID"],
        "sandikId": "",
        "sorguTuru": "",
    }


def fetch_district(district: dict, refresh: bool) -> tuple[dict, list, list]:
    district_id = f"{district['il_ID']}_{district['secim_CEVRESI_ID']}"
    headers = load_or_fetch(
        RAW / f"{district_id}_headers.json",
        "getIttifakSecimSonucBaslikList",
        refresh,
        secimId=SECIM_ID,
        secimCevresiId=district["secim_CEVRESI_ID"],
        ilId=district["il_ID"],
        bagimsiz=1,
    )
    rows = load_or_fetch(
        RAW / f"{district_id}_rows.json",
        "getSecimSandikSonucList",
        refresh,
        **district_params(district),
    )
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{district['il_ADI']}: no rows returned")
    return district, headers, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    districts = get("getIlList", secimId=SECIM_ID, secimTuru=SECIM_TURU)
    if args.limit:
        districts = districts[: args.limit]
    print(f"{len(districts)} electoral districts, {sum(d['secilecek_ADAY_SAYISI'] for d in districts)} seats")

    header_rows: list[dict] = []
    long_rows: list[dict] = []
    district_rows: list[dict] = []
    ilce_rows: list[dict] = []

    party_names: dict[str, str] = {}
    independent_names: dict[str, str] = {}

    for i, district in enumerate(districts, 1):
        district["seats"] = district["secilecek_ADAY_SAYISI"]
        district_id = f"{district['il_ID']}_{district['secim_CEVRESI_ID']}"
        d, headers, rows = fetch_district(district, args.refresh)

        for h in headers:
            col = h["column_NAME"]
            kind = "party" if col.startswith("parti") else "independent"
            pid = ("P" if kind == "party" else "I") + str(h["sira_NO"])
            if kind == "party":
                party_names.setdefault(pid, h["ad"])
            else:
                independent_names[f"{district_id}:{pid}"] = h["ad"]
            header_rows.append(
                {
                    "district_id": district_id,
                    "party_id": pid,
                    "kind": kind,
                    "sira_no": h["sira_NO"],
                    "name": h["ad"],
                    "column_name": col,
                }
            )
        for n, name in ALLIANCE_NAMES.items():
            header_rows.append(
                {
                    "district_id": district_id,
                    "party_id": f"A{n}",
                    "kind": "joint_list",
                    "sira_no": n,
                    "name": name,
                    "column_name": f"ittifak{n}_ALDIGI_OY",
                }
            )

        valid_votes = sum(int(r.get("gecerli_OY_TOPLAMI") or 0) for r in rows)
        ballots = sum(int(r.get("oy_KULLANAN_SECMEN_SAYISI") or 0) for r in rows)
        electorate = sum(int(r.get("secmen_SAYISI") or 0) for r in rows)

        votes: dict[str, int] = {}
        for r in rows:
            for n in range(1, 25):
                key = f"P{n}"
                votes[key] = votes.get(key, 0) + int(r.get(f"parti{n}_ALDIGI_OY") or 0)
            for n in range(1, 51):
                key = f"I{n}"
                votes[key] = votes.get(key, 0) + int(r.get(f"bagimsiz{n}_ALDIGI_OY") or 0)
            for n in range(1, 6):
                key = f"A{n}"
                votes[key] = votes.get(key, 0) + int(r.get(f"ittifak{n}_ALDIGI_OY") or 0)

            for n in range(1, 25):
                ilce_rows.append(
                    {
                        "district_id": district_id,
                        "ilce_id": r.get("ilce_ID"),
                        "ilce": r.get("ilce_ADI"),
                        "party_id": f"P{n}",
                        "votes": int(r.get(f"parti{n}_ALDIGI_OY") or 0),
                        "valid_votes": int(r.get("gecerli_OY_TOPLAMI") or 0),
                    }
                )

        total_votes = sum(votes.values())
        if total_votes != valid_votes:
            print(
                f"  WARN {district['il_ADI']}: party+independent={total_votes} "
                f"valid={valid_votes} diff={valid_votes - total_votes}"
            )

        row = {
            "district_id": district_id,
            "province": d["il_ADI"],
            "il_id": d["il_ID"],
            "secim_cevresi_id": d["secim_CEVRESI_ID"],
            "seats": d["seats"],
            "valid_votes": valid_votes,
            "ballots_cast": ballots,
            "electorate": electorate,
        }
        row.update(votes)
        district_rows.append(row)

        for pid, nvotes in votes.items():
            if nvotes == 0:
                continue
            if pid.startswith("A"):
                name = ALLIANCE_NAMES[int(pid[1:])]
            else:
                name = party_names.get(pid) or independent_names.get(
                    f"{district_id}:{pid}", pid
                )
            long_rows.append(
                {
                    "district_id": district_id,
                    "province": d["il_ADI"],
                    "party_id": pid,
                    "party_name": name,
                    "votes": nvotes,
                    "valid_votes": valid_votes,
                    "seats": d["seats"],
                }
            )

        print(f"[{i}/{len(districts)}] {d['il_ADI']}: {len(rows)} ilce, {valid_votes} valid votes")

    wide = pd.DataFrame(district_rows)
    # Keep the ID columns predictable and drop all-zero independent columns.
    party_cols = [f"P{n}" for n in range(1, 25)]
    indep_cols = [f"I{n}" for n in range(1, 51)]
    indep_cols = [c for c in indep_cols if c in wide.columns and wide[c].sum() > 0]
    joint_cols = [f"A{n}" for n in range(1, 6)]
    joint_cols = [c for c in joint_cols if c in wide.columns and wide[c].sum() > 0]
    keep = (
        ["district_id", "province", "il_id", "secim_cevresi_id", "seats",
         "valid_votes", "ballots_cast", "electorate"]
        + party_cols
        + indep_cols
        + joint_cols
    )
    wide = wide[[c for c in keep if c in wide.columns]]
    wide.to_csv(PROCESSED / "parliament_2023_districts.csv", index=False)

    pd.DataFrame(long_rows).to_csv(
        PROCESSED / "parliament_2023_long.csv", index=False
    )
    pd.DataFrame(ilce_rows).to_csv(
        PROCESSED / "parliament_2023_ilce.csv", index=False
    )
    pd.DataFrame(header_rows).drop_duplicates(
        subset=["district_id", "party_id"]
    ).to_csv(PROCESSED / "party_headers_2023.csv", index=False)

    seats = wide[["district_id", "province", "seats"]].copy()
    seats.to_csv(PROCESSED / "seat_counts_2023.csv", index=False)

    actual = get("getPartiKazanimSayisi", secimId=SECIM_ID, secimTuru=SECIM_TURU)
    by_name = {norm(name): pid for pid, name in party_names.items()}
    actual_rows = []
    for item in actual:
        key = norm(item["parti_KISA_ADI"])
        actual_rows.append(
            {
                "party_id": by_name.get(key, key),
                "party": item["parti_KISA_ADI"],
                "seats": int(item["sayi"]),
            }
        )
    pd.DataFrame(actual_rows).to_csv(
        PROCESSED / "actual_seats_2023.csv", index=False
    )

    province_rows = []
    for il_id in sorted({int(x) for x in wide["il_id"]}):
        province = wide.loc[wide["il_id"] == il_id, "province"].iloc[0].split("-")[0]
        for item in get(
            "getPartiKazanimSayisiIl",
            secimId=SECIM_ID,
            secimTuru=SECIM_TURU,
            ilId=il_id,
        ):
            key = norm(item["parti_KISA_ADI"])
            province_rows.append(
                {
                    "il_id": il_id,
                    "province": province,
                    "party_id": by_name.get(key, key),
                    "party": item["parti_KISA_ADI"],
                    "seats": int(item["sayi"]),
                }
            )
        time.sleep(0.15)
    pd.DataFrame(province_rows).to_csv(
        PROCESSED / "actual_seats_2023_by_province.csv", index=False
    )

    print(f"\n{len(wide)} districts, {int(wide['seats'].sum())} seats")
    print(f"national valid votes: {int(wide['valid_votes'].sum()):,}")
    print(f"actual seats: {sum(r['seats'] for r in actual_rows)}")
    print(f"wrote {PROCESSED}/parliament_2023_*.csv")


if __name__ == "__main__":
    main()
