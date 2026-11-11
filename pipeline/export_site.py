"""Build the JSON the static site consumes.

    uv run python pipeline/export_site.py

Reads the processed 2023 parliamentary data, folds joint-list votes into the
alliance's largest member in each district (the same rule the Python allocator
uses), and writes web/data/parliament_2023.json. Poll files are exported for
each available election year (2023, 2028).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
WEB_DATA = ROOT / "web" / "data"
GEO = ROOT / "web" / "geo" / "tr-provinces.geojson"
ILCE_GEO = ROOT / "web" / "geo" / "tr-ilce.geojson"

PARTY_META = {
    "P9": {"name": "Adalet ve Kalkınma Partisi", "short": "AK Parti", "color": "#F4A300", "seat_order": 80, "main_order": 10, "main": True},
    "P21": {"name": "Cumhuriyet Halk Partisi", "short": "CHP", "color": "#E4002B", "seat_order": 30, "main_order": 20, "main": True},
    "P11": {"name": "Milliyetçi Hareket Partisi", "short": "MHP", "color": "#8B1A1A", "seat_order": 90, "main_order": 30, "main": True},
    "P22": {"name": "İYİ Parti", "short": "İYİ Parti", "color": "#2E6DB4", "seat_order": 40, "main_order": 40, "main": True},
    "P12": {"name": "Yeşiller ve Sol Gelecek Partisi", "short": "Yeşil Sol", "color": "#2E7D32", "seat_order": 20, "main_order": 50, "main": True},
    "P10": {"name": "Yeniden Refah Partisi", "short": "YRP", "color": "#00897B", "seat_order": 70, "main_order": 60, "main": True},
    "P13": {"name": "Türkiye İşçi Partisi", "short": "TİP", "color": "#C2185B", "seat_order": 10, "main_order": 70, "main": True},
    "P24": {"name": "Zafer Partisi", "short": "Zafer", "color": "#1E3A8A", "seat_order": 60, "main_order": 80, "main": True},
    "P8": {"name": "Büyük Birlik Partisi", "short": "BBP", "color": "#6D4C41", "seat_order": 95, "main_order": 85, "main": True},
}
ALLIANCE_LABELS = {
    "CUMHUR": "Cumhur İttifakı",
    "MILLET": "Millet İttifakı",
    "EMEK_VE_OZGURLUK": "Emek ve Özgürlük İttifakı",
    "ATA": "ATA İttifakı",
    "SOSYALIST_GUC_BIRLIGI": "Sosyalist Güç Birliği",
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


def main() -> None:
    cfg = OmegaConf.to_container(
        OmegaConf.load(ROOT / "config" / "alliances_2023.yaml"), resolve=True
    )
    alliances = {k: list(v) for k, v in cfg["alliances"].items()}
    joint_lists = dict(cfg.get("joint_lists") or {})
    threshold = float(cfg["threshold"])
    cfg_2028 = OmegaConf.to_container(
        OmegaConf.load(ROOT / "config" / "alliances_2028.yaml"), resolve=True
    )
    alliances_2028 = {k: list(v) for k, v in cfg_2028["alliances"].items()}
    joint_lists_2028 = dict(cfg_2028.get("joint_lists") or {})
    threshold_2028 = float(cfg_2028["threshold"])

    wide = pd.read_csv(PROCESSED / "parliament_2023_districts.csv")
    headers = pd.read_csv(PROCESSED / "party_headers_2023.csv")
    actual = pd.read_csv(PROCESSED / "actual_seats_2023.csv")

    header_names = (
        headers[headers["party_id"].str.startswith("P")]
        .drop_duplicates("party_id")
        .set_index("party_id")["name"]
        .to_dict()
    )
    actual_seats = dict(zip(actual["party_id"], actual["seats"].astype(int)))

    party_to_alliance = {}
    for alliance, members in alliances.items():
        for party in members:
            party_to_alliance[party] = alliance

    parties = []
    all_party_ids = [f"P{n}" for n in range(1, 25)]
    for pid in all_party_ids:
        meta = PARTY_META.get(pid, {})
        name = meta.get("name", header_names.get(pid, pid))
        short = meta.get("short", header_names.get(pid, pid))
        parties.append(
            {
                "id": pid,
                "name": name,
                "short": short,
                "color": meta.get("color", "#9E9E9E"),
                "seat_order": meta.get("seat_order", 100),
                "main_order": meta.get("main_order"),
                "main": bool(meta.get("main", False)),
                "alliance": party_to_alliance.get(pid),
                "actual_seats": int(actual_seats.get(pid, 0)),
            }
        )

    extra_parties = OmegaConf.to_container(
        OmegaConf.load(ROOT / "config" / "parties_2028.yaml"), resolve=True
    )["parties"]
    for pid, meta in extra_parties.items():
        parties.append(
            {
                "id": pid,
                "name": meta["name"],
                "short": meta["short"],
                "color": meta["color"],
                "seat_order": meta.get("seat_order", 100),
                "main_order": meta.get("main_order"),
                "main": bool(meta.get("main", False)),
                "active_from": int(meta.get("active_from", 2028)),
                "baseline_mix": meta.get("baseline_mix", {}),
                "alliance": None,
                "actual_seats": 0,
            }
        )

    p_cols = [f"P{n}" for n in range(1, 25)]
    a_cols = [f"A{n}" for n in range(1, 6)]
    i_cols = [c for c in wide.columns if c.startswith("I")]

    districts = []
    for _, row in wide.iterrows():
        votes = {pid: int(row[pid]) for pid in p_cols if int(row[pid]) != 0}
        joint = {aid: int(row[aid]) for aid in a_cols if aid in row and int(row[aid]) != 0}
        independents = {iid: int(row[iid]) for iid in i_cols if int(row[iid]) != 0}

        # Fold joint-list votes into the alliance's largest member in this district.
        effective = dict(votes)
        for aid, n in joint.items():
            alliance = joint_lists.get(aid)
            members = alliances.get(alliance, [])
            members_with_votes = [p for p in members if votes.get(p, 0) > 0]
            host = (
                max(members_with_votes, key=lambda p: votes[p])
                if members_with_votes
                else (members[0] if members else None)
            )
            if host:
                effective[host] = effective.get(host, 0) + n

        province = row["province"]
        districts.append(
            {
                "id": row["district_id"],
                "province": province,
                "province_base": province.split("-")[0],
                "il_id": int(row["il_id"]),
                "secim_cevresi_id": int(row["secim_cevresi_id"]),
                "seats": int(row["seats"]),
                "valid_votes": int(row["valid_votes"]),
                "ballots_cast": int(row["ballots_cast"]),
                "electorate": int(row["electorate"]),
                "votes": effective,
                "raw_votes": votes,
                "joint": joint,
                "independents": independents,
            }
        )

    province_map = {}
    for d in districts:
        key = d["province_base"]
        p = province_map.setdefault(
            key,
            {
                "name": key,
                "geo_key": norm(key),
                "il_id": d["il_id"],
                "seats": 0,
                "valid_votes": 0,
                "ballots_cast": 0,
                "electorate": 0,
                "votes": {},
            },
        )
        p["seats"] += d["seats"]
        p["valid_votes"] += d["valid_votes"]
        p["ballots_cast"] += d["ballots_cast"]
        p["electorate"] += d["electorate"]
        for pid, n in d["votes"].items():
            p["votes"][pid] = p["votes"].get(pid, 0) + n

    provinces = []
    for p in province_map.values():
        total = sum(p["votes"].values())
        p["shares"] = {pid: n / total for pid, n in p["votes"].items()} if total else {}
        p["winner"] = max(p["votes"], key=p["votes"].get) if p["votes"] else None
        p["turnout"] = p["ballots_cast"] / p["electorate"] if p["electorate"] else 0
        provinces.append(p)
    provinces.sort(key=lambda x: x["name"])

    # Ilce-level votes for the finer map. Seat allocation stays at the
    # electoral-district level; this is a visualization layer.
    ilce_raw = pd.read_csv(PROCESSED / "parliament_2023_ilce.csv")
    ilce_map = pd.read_csv(PROCESSED / "ilce_geo_mapping.csv")
    district_lookup = wide[["district_id", "il_id", "province"]].drop_duplicates()
    ilce_raw = ilce_raw.merge(district_lookup, on="district_id", how="left")
    ilce_raw = ilce_raw.merge(
        ilce_map[
            ["il_id", "ilce_id", "geo_shape_id", "geo_shape_name", "geo_province"]
        ],
        on=["il_id", "ilce_id"],
        how="left",
    )
    if ilce_raw["geo_shape_id"].isna().any():
        missing = ilce_raw.loc[
            ilce_raw["geo_shape_id"].isna(), ["il_id", "ilce_id", "ilce"]
        ].drop_duplicates()
        raise SystemExit(f"unmapped ilce: {missing.to_dict('records')}")

    ilce_records = []
    grouped = ilce_raw.groupby(
        [
            "district_id",
            "il_id",
            "ilce_id",
            "ilce",
            "province",
            "geo_shape_id",
            "geo_shape_name",
            "geo_province",
        ],
        dropna=False,
    )
    for keys, group in grouped:
        (
            district_id,
            il_id,
            ilce_id,
            ilce_name,
            province,
            geo_id,
            geo_name,
            geo_province,
        ) = keys
        votes = {
            row["party_id"]: int(row["votes"])
            for _, row in group.iterrows()
            if int(row["votes"]) != 0
        }
        ilce_records.append(
            {
                "geo_id": geo_id,
                "name": ilce_name,
                "geo_name": geo_name,
                "province": geo_province,
                "province_key": norm(geo_province),
                "province_base": province.split("-")[0],
                "district_id": district_id,
                "il_id": int(il_id),
                "ilce_id": int(ilce_id),
                "valid_votes": int(group["valid_votes"].iloc[0]),
                "votes": votes,
            }
        )
    if len(ilce_records) != 973:
        raise SystemExit(f"expected 973 ilce, got {len(ilce_records)}")
    geo_ilce = json.loads(ILCE_GEO.read_text(encoding="utf-8"))
    geo_ids = {feature["properties"]["shapeID"] for feature in geo_ilce["features"]}
    missing_geo = {record["geo_id"] for record in ilce_records} - geo_ids
    if missing_geo:
        raise SystemExit(f"ilce geo ids not in GeoJSON: {sorted(missing_geo)[:5]}")

    president = pd.read_csv(PROCESSED / "president_2023.csv")
    if len(president) != 81:
        raise SystemExit(f"expected 81 presidential provinces, got {len(president)}")

    pres_candidates = [
        {
            "id": "A",
            "name": "Recep Tayyip Erdoğan",
            "short": "Erdoğan",
            "color": "#F4A300",
        },
        {
            "id": "B",
            "name": "Kemal Kılıçdaroğlu",
            "short": "Kılıçdaroğlu",
            "color": "#E4002B",
        },
        {
            "id": "C",
            "name": "Sinan Oğan",
            "short": "Oğan",
            "color": "#6D4C41",
        },
        {
            "id": "D",
            "name": "Muharrem İnce",
            "short": "İnce",
            "color": "#2E6DB4",
        },
    ]

    def president_round(prefix, candidate_ids, columns):
        records = []
        national = {candidate: 0 for candidate in candidate_ids}
        for _, row in president.iterrows():
            votes = {
                candidate: int(row[column])
                for candidate, column in zip(candidate_ids, columns)
            }
            valid = int(row[f"{prefix}_valid"])
            for candidate, value in votes.items():
                national[candidate] += value
            records.append(
                {
                    "name": row["province"],
                    "geo_key": norm(row["province"]),
                    "votes": votes,
                    "shares": {
                        candidate: value / valid if valid else 0
                        for candidate, value in votes.items()
                    },
                    "winner": max(votes, key=votes.get) if votes else None,
                    "valid_votes": valid,
                    "ballots_cast": int(row[f"{prefix}_ballots"]),
                    "electorate": int(row[f"{prefix}_electorate"]),
                    "turnout": (
                        int(row[f"{prefix}_ballots"]) / int(row[f"{prefix}_electorate"])
                        if int(row[f"{prefix}_electorate"])
                        else 0
                    ),
                }
            )
        total = sum(national.values())
        return {
            "national": {
                "votes": national,
                "shares": {
                    candidate: value / total if total else 0
                    for candidate, value in national.items()
                },
            },
            "provinces": records,
        }

    first_round = president_round(
        "first", ["A", "B", "C", "D"], ["first_A", "first_B", "first_C", "first_D"]
    )
    runoff = president_round("runoff", ["A", "B"], ["runoff_A", "runoff_B"])
    first_shares = first_round["national"]["shares"]
    runoff_shares = runoff["national"]["shares"]
    eliminated = [c for c in ("C", "D") if first_shares.get(c, 0) > 0]
    eliminated_total = sum(first_shares[c] for c in eliminated)
    transfer_default = (
        (runoff_shares["A"] - first_shares["A"]) / eliminated_total
        if eliminated_total
        else 0.5
    )
    transfer_default = min(1.0, max(0.0, transfer_default))

    national_votes = {}
    for p in provinces:
        for pid, n in p["votes"].items():
            national_votes[pid] = national_votes.get(pid, 0) + n
    national_total = sum(national_votes.values())

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    geo_keys = {norm(f["properties"]["shapeName"]) for f in geo["features"]}
    data_keys = {p["geo_key"] for p in provinces}
    missing = sorted(data_keys - geo_keys)
    extra = sorted(geo_keys - data_keys)
    if missing or extra:
        raise SystemExit(f"GeoJSON mismatch: missing={missing} extra={extra}")

    payload = {
        "meta": {
            "project": "DATAM",
            "election": "2023 Milletvekili Genel Seçimi",
            "election_id": int(cfg["election_id"]),
            "threshold": threshold,
            "alliances": alliances,
            "alliances_2028": alliances_2028,
            "threshold_2028": threshold_2028,
            "alliance_labels": ALLIANCE_LABELS,
            "joint_lists": joint_lists,
            "joint_lists_2028": joint_lists_2028,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "YSK açık veri; TÜİK NİP",
            "disclaimer": "Bu araç bir senaryo simülasyonudur; seçim tahmini değildir.",
        },
        "parties": parties,
        "districts": districts,
        "provinces": provinces,
        "ilce": ilce_records,
        "president": {
            "candidates": pres_candidates,
            "first_round": first_round,
            "runoff": runoff,
            "transfer_default": transfer_default,
        },
        "national": {
            "valid_votes": national_total,
            "votes": national_votes,
            "shares": {
                pid: n / national_total for pid, n in national_votes.items()
            }
            if national_total
            else {},
            "actual_seats": actual_seats,
        },
    }

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    out = WEB_DATA / "parliament_2023.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"wrote {out} ({out.stat().st_size/1024:.1f} KB): "
        f"{len(districts)} districts, {len(provinces)} provinces, "
        f"{sum(p['seats'] for p in provinces)} seats"
    )

    for year in (2023, 2028):
        poll_files = {
            "president": ROOT / "polls" / f"{year}_president.json",
            "parliament": ROOT / "polls" / f"{year}_parliament.json",
        }
        poll_payload = {
            "meta": {
                "source": "Turkish Wikipedia" if year == 2023 else "pending",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "datasets": {},
        }
        for key, path in poll_files.items():
            if path.exists():
                poll_payload["datasets"][key] = json.loads(path.read_text(encoding="utf-8"))
        if poll_payload["datasets"]:
            poll_out = WEB_DATA / f"polls_{year}.json"
            poll_out.write_text(
                json.dumps(poll_payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            print(f"wrote {poll_out} ({poll_out.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
