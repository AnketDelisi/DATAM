"""Scrape 2028 parliamentary polls from Turkish Wikipedia.

    python pipeline/scrape_2028_polls.py

The source page has separate tables for 2026, 2025, 2024, and 2023. The 2026
table includes YENI (YEP) and A. Missing party cells are omitted; the app
treats them as absent rather than zero.
"""

from __future__ import annotations

import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.scrape_historical_polls import (
    AliasMap,
    EXCLUDE_POLLSTERS,
    EXCLUDE_POLLSTER_WORDS,
    clean_pollster,
    load_yaml,
    norm,
    parse_date,
    slug,
    to_num,
    to_sample,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "polls" / "2028_parliament.json"
URL = "https://tr.wikipedia.org/wiki/Bir_sonraki_T%C3%BCrkiye_genel_se%C3%A7imleri_i%C3%A7in_yap%C4%B1lan_anketler"
TABLE_YEARS = {2: 2026, 4: 2025, 6: 2024, 8: 2023}
PARTY_COLUMNS = {
    "AKP": "P9",
    "CHP": "P21",
    "MHP": "P11",
    "İYİ": "P22",
    "DEM": "P12",
    "YRP": "P10",
    "ZP": "P24",
    "TİP": "P13",
    "A": "A",
    "YEP": "YENI",
    "Diğer": "OTHER",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def maps() -> tuple[AliasMap, AliasMap]:
    entities = load_yaml("entities.yaml")["parties"]
    party_aliases = {
        party_id: [party["name"], *party.get("aliases", [])]
        for party_id, party in entities.items()
    }
    party_aliases["OTHER"] = [*party_aliases.get("OTHER", []), "DIGER", "BAGIMSIZ"]
    pollsters = load_yaml("pollsters.yaml")["pollsters"]
    pollster_aliases = {
        canonical: [canonical, *aliases] for canonical, aliases in pollsters.items()
    }
    return AliasMap(party_aliases), AliasMap(pollster_aliases)


def parse_table(table: pd.DataFrame, year: int, party_map: AliasMap, pollster_map: AliasMap, used_ids: set[str]) -> list[dict]:
    polls = []
    for _, row in table.iterrows():
        date_text = str(row.get("Tarih", ""))
        if not date_text or norm(date_text) == "tarih":
            continue
        parsed = parse_date(date_text, year)
        if not parsed:
            continue
        field_start, field_end, precision = parsed
        if field_end.year < 2023:
            continue
        pollster = clean_pollster(str(row.get("Anket şirketi", "")))
        if not pollster or pollster in EXCLUDE_POLLSTERS:
            continue
        pollster_norm = norm(pollster)
        if any(norm(word) in pollster_norm for word in EXCLUDE_POLLSTER_WORDS):
            continue
        pollster = pollster_map.match(pollster) or pollster
        results = {}
        for column, party_id in PARTY_COLUMNS.items():
            if column not in table.columns:
                continue
            value = to_num(row.get(column))
            if value is None:
                continue
            if value < 0 or value > 100:
                continue
            results[party_id] = value / 100
        if len(results) < 2:
            continue
        total = sum(results.values())
        if total < 0.5 or total > 1.2:
            continue
        base_id = f"2028_{field_end.isoformat()}_{slug(pollster)}_parliamentary_national"
        poll_id = base_id
        suffix = 2
        while poll_id in used_ids:
            poll_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(poll_id)
        polls.append({
            "poll_id": poll_id,
            "pollster": pollster,
            "field_start": field_start.isoformat(),
            "field_end": field_end.isoformat(),
            "date_precision": precision,
            "sample_size": to_sample(row.get("Örneklem")),
            "method": None,
            "population": "adult",
            "type": "parliamentary",
            "round": None,
            "results": results,
            "undecided": None,
            "source_url": URL,
            "source_page": "tr.wikipedia.org",
            "source_date_text": date_text,
            "source_pollster_text": pollster,
            "status": "published",
            "notes": "Wikipedia 2028 polling table; YEP mapped to YENI",
        })
    return polls


def main() -> None:
    html = fetch(URL)
    tables = pd.read_html(io.StringIO(html), header=0, decimal=",", thousands=None)
    party_map, pollster_map = maps()
    used_ids: set[str] = set()
    polls = []
    for index, year in TABLE_YEARS.items():
        polls.extend(parse_table(tables[index], year, party_map, pollster_map, used_ids))
    polls.sort(key=lambda poll: (poll["field_end"], poll["pollster"], poll["poll_id"]))
    payload = {
        "meta": {
            "source": URL,
            "coverage": "2028 parliamentary polls from Turkish Wikipedia",
            "unit": "fraction",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "party_map": PARTY_COLUMNS,
            "note": "Missing party cells are omitted; YEP is Yeni Parti.",
        },
        "polls": polls,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(polls)} polls)")


if __name__ == "__main__":
    main()
