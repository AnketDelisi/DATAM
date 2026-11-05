"""Scrape Turkish historical election polls from Wikipedia.

    python pipeline/scrape_historical_polls.py

Outputs one file per election under ``polls/historical/`` plus a coverage
summary.  The scraper is deliberately conservative: it only emits polls whose
date, pollster and at least two entity shares can be identified.  Party names
are canonicalised with ``config/entities.yaml`` and pollsters with
``config/pollsters.yaml``.
"""

from __future__ import annotations

import calendar
import io
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "polls" / "historical"
CONFIG_DIR = ROOT / "config"

MONTHS = {
    "ocak": 1, "oca": 1,
    "şubat": 2, "subat": 2, "şub": 2, "sub": 2,
    "mart": 3, "mar": 3,
    "nisan": 4, "nis": 4,
    "mayıs": 5, "mayis": 5, "may": 5,
    "haziran": 6, "haz": 6,
    "temmuz": 7, "tem": 7,
    "ağustos": 8, "agustos": 8, "ağu": 8, "agu": 8,
    "eylül": 9, "eylul": 9, "eyl": 9,
    "ekim": 10, "eki": 10,
    "kasım": 11, "kasim": 11, "kas": 11,
    "aralık": 12, "aralik": 12, "ara": 12,
}

EXCLUDE_POLLSTER_WORDS = [
    "ortalama", "seçim sonucu", "secim sonucu", "gerçekleşen",
    "gerceklesen", "açıklanan", "aciklanan", "sandık", "sandik",
    "tahmin", "model", "sonuç", "sonuc", "kesin", "resmî", "resmi",
    "genel secim", "secimler", "secim sonuc",
]

NATIONAL_RACE_NOTES = {
    "parliamentary": "national parliamentary vote share",
    "presidential_first": "national first-round presidential vote share",
    "presidential_runoff": "national runoff presidential vote share",
    "referendum": "national referendum vote share",
}


def norm(value: str) -> str:
    text = value.lower()
    text = (
        text.replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("â", "a")
        .replace("î", "i")
        .replace("û", "u")
    )
    return re.sub(r"\s+", " ", text).strip()


def slug(value: str) -> str:
    text = norm(value)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "poll"


def is_nan(value) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def clean_text(value) -> str:
    text = re.sub(r"\[[^\]]*\]", "", str(value))
    text = re.sub(r"\((?:[^)]*)\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


POLLSTER_MAP: AliasMap | None = None
EXCLUDE_POLLSTERS = {"CHP", "AKP", "MHP", "HDP", "IYI", "SP", "BBP", "DP"}


def clean_pollster(value) -> str:
    text = clean_text(value)
    text = re.sub(r"\b\d{1,2}\s+\w+\s+\d{4}\s+tarihinde.*$", "", text, flags=re.I)
    text = re.sub(r"Wayback Machine.*$", "", text, flags=re.I)
    text = re.sub(r"\s+(?:tarihinde|arşivlendi|arsivlendi).*$", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" .,-")


def canonical_pollster(text: str) -> str:
    if POLLSTER_MAP:
        matched = POLLSTER_MAP.match(text)
        if matched:
            return matched
    return text


def to_num(value) -> float | None:
    if value is None or is_nan(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    if text in {"–", "-", "—", ""}:
        return None
    text = text.replace("%", "").replace(" ", "").replace("\u00a0", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def to_sample(value) -> int | None:
    if value is None or is_nan(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    if text in {"–", "-", "—", ""}:
        return None
    text = text.replace(".", "").replace(",", "").replace(" ", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def month_number(token: str) -> int | None:
    token = norm(token)
    for key, value in MONTHS.items():
        if token.startswith(key):
            return value
    return None


def parse_date(text: str, default_year: int):
    text = re.sub(r"\[[^\]]*\]", "", str(text)).strip().lower()
    match = re.search(r"(20\d{2})", text)
    year = int(match.group(1)) if match else default_year

    same_month = re.search(
        r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([a-zçğıöşü]+)", text
    )
    if same_month:
        month = month_number(same_month.group(3))
        if month:
            start = date(year, month, int(same_month.group(1)))
            end = date(year, month, int(same_month.group(2)))
            return start, end, "day"

    cross_month = re.search(
        r"(\d{1,2})\s+([a-zçğıöşü]+)\s*[-–]\s*(\d{1,2})\s+([a-zçğıöşü]+)",
        text,
    )
    if cross_month:
        month1 = month_number(cross_month.group(2))
        month2 = month_number(cross_month.group(4))
        if month1 and month2:
            start = date(year, month1, int(cross_month.group(1)))
            end = date(year, month2, int(cross_month.group(3)))
            return start, end, "day"

    single = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)", text)
    if single:
        month = month_number(single.group(2))
        if month:
            day = int(single.group(1))
            return date(year, month, day), date(year, month, day), "day"

    month_only = re.search(r"([a-zçğıöşü]+)", text)
    if month_only:
        month = month_number(month_only.group(1))
        if month:
            last = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last), "month"

    return None


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def read_tables(html: str) -> list[pd.DataFrame]:
    return pd.read_html(io.StringIO(html), header=None, decimal=",", thousands=None)


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class AliasMap:
    def __init__(self, mapping: dict[str, list[str]]):
        self.mapping = mapping
        self.items: list[tuple[str, str]] = []
        for canonical, aliases in mapping.items():
            for alias in aliases:
                key = norm(str(alias))
                if key:
                    self.items.append((key, canonical))
        self.items.sort(key=lambda item: len(item[0]), reverse=True)

    def match(self, header: str) -> str | None:
        text = norm(header)
        for alias, canonical in self.items:
            if alias == text or alias in text:
                return canonical
        return None

    def subset(self, allowed: set[str]) -> "AliasMap":
        return AliasMap({key: value for key, value in self.mapping.items() if key in allowed})


def build_entities(entities_cfg: dict):
    party_aliases: dict[str, list[str]] = {}
    for party_id, party in entities_cfg["parties"].items():
        party_aliases[party_id] = [party["name"], *party.get("aliases", [])]
    party_aliases["OTHER"] = party_aliases.get("OTHER", []) + ["DIGER", "BAGIMSIZ", "BAG", "BAG."]
    party_aliases["YES"] = ["EVET", "YES"]
    party_aliases["NO"] = ["HAYIR", "NO"]

    candidate_aliases: dict[str, list[str]] = {}
    for cand_id, cand in entities_cfg["candidates"].items():
        candidate_aliases[cand_id] = [cand["name"], *cand.get("aliases", [])]

    return AliasMap(party_aliases), AliasMap(candidate_aliases)


def header_info(df: pd.DataFrame):
    def from_columns():
        if df.shape[1] == 0:
            return None
        headers = []
        for col in df.columns:
            parts = col if isinstance(col, tuple) else (col,)
            cleaned = []
            for part in parts:
                text = re.sub(r"Unnamed:.*", "", str(part)).strip()
                if text and text.lower() not in {"nan", "none"}:
                    cleaned.append(text)
            headers.append(" ".join(dict.fromkeys(cleaned)))
        joined = " ".join(norm(h) for h in headers)
        if ("tarih" in joined or "yapilis" in joined) and "anket" in joined:
            return [], headers, 0
        return None

    from_cols = from_columns()
    if from_cols:
        return from_cols

    header_rows = []
    for i in range(min(4, len(df))):
        joined = " ".join(norm(str(v)) for v in df.iloc[i].tolist())
        if ("tarih" in joined or "yapilis" in joined) and "anket" in joined:
            header_rows.append(i)
            if i + 1 < len(df):
                nxt = " ".join(norm(str(v)) for v in df.iloc[i + 1].tolist())
                if any(k in nxt for k in ("evet", "hayir", "akp", "ak parti", "chp", "mhp", "hdp", "iyi", "sp", "dem")):
                    header_rows.append(i + 1)
            break
    if not header_rows:
        return None

    headers = []
    for col in range(df.shape[1]):
        parts = []
        for row in header_rows:
            value = df.iat[row, col]
            if not is_nan(value):
                text = re.sub(r"Unnamed:.*", "", str(value)).strip()
                if text:
                    parts.append(text)
        headers.append(" ".join(dict.fromkeys(parts)))

    last_header = max(header_rows)
    return header_rows, headers, last_header + 1


def column_lookup(headers: list[str]):
    def find(*needles):
        for index, header in enumerate(headers):
            text = norm(header)
            if any(norm(n) in text for n in needles):
                return index
        return None

    return {
        "date": find("tarih", "yapilis"),
        "pollster": find("anketi yapan", "anket sirketi", "anket"),
        "sample": find("katilimci", "orneklem", "örneklem"),
    }


def parse_scope(text: str) -> str | None:
    text = norm(text)
    if any(word in text for word in ("buyuksehir", "büyükşehir")):
        return "metropolitan_mayor"
    if "il genel meclisi" in text:
        return "provincial_council"
    if "belediye meclisi" in text or "belediye meclis" in text:
        return "municipal_council"
    if "belediye baskan" in text or "belediye başkan" in text:
        return "mayor"
    return None


def parse_table(
    df: pd.DataFrame,
    *,
    election_key: str,
    election_cfg: dict,
    race: str,
    race_entities: set[str] | None,
    scope: str,
    scope_type: str,
    race_type: str | None,
    source_url: str,
    party_map: AliasMap,
    candidate_map: AliasMap,
    used_ids: set[str],
) -> list[dict]:
    info = header_info(df)
    if not info:
        return []
    header_rows, headers, data_start = info
    joined_headers = norm(" ".join(headers))
    if any(word in joined_headers for word in ("cogunluk", "milletvekili", "sandalye")):
        return []
    if "cumhur ittifaki" in joined_headers or "millet ittifaki" in joined_headers:
        return []
    if len(headers) < 3:
        return []

    cols = column_lookup(headers)
    if cols["date"] is None or cols["pollster"] is None:
        return []

    allowed = race_entities or set()
    if race.startswith("presidential") and allowed:
        aliases = candidate_map.subset(allowed)
    else:
        aliases = party_map

    entity_cols: list[tuple[int, str]] = []
    for index, header in enumerate(headers):
        if index in {cols["date"], cols["pollster"], cols["sample"]}:
            continue
        entity = aliases.match(header)
        if not entity:
            continue
        if allowed:
            if entity not in allowed:
                if entity in {"YES", "NO"}:
                    continue
                if "OTHER" in allowed:
                    entity = "OTHER"
                else:
                    continue
        entity_cols.append((index, entity))

    if len(entity_cols) < 2:
        return []

    election_date = date.fromisoformat(election_cfg["date"])
    runoff_date = election_cfg.get("runoff_date")
    max_date = date.fromisoformat(runoff_date) if runoff_date and race.endswith("runoff") else election_date
    start_date = date.fromisoformat(election_cfg["start_date"])

    polls = []
    for _, row in df.iloc[data_start:].iterrows():
        date_text = row.iloc[cols["date"]]
        if is_nan(date_text) or not str(date_text).strip():
            continue
        parsed = parse_date(date_text, election_date.year)
        if not parsed:
            continue
        field_start, field_end, precision = parsed
        if field_end < start_date or field_end > max_date:
            continue

        pollster = clean_pollster(row.iloc[cols["pollster"]])
        if not pollster:
            continue
        pollster = canonical_pollster(pollster)
        pollster_norm = norm(pollster)
        if pollster in EXCLUDE_POLLSTERS:
            continue
        if any(norm(word) in pollster_norm for word in EXCLUDE_POLLSTER_WORDS):
            continue

        results: dict[str, float] = {}
        invalid = False
        for index, entity in entity_cols:
            raw = to_num(row.iloc[index])
            if raw is None:
                continue
            if raw > 100:
                invalid = True
                break
            results[entity] = raw / 100.0
        if invalid or len(results) < 2:
            continue
        total = sum(results.values())
        if total < 0.5 or total > 1.5:
            continue

        base_id = f"{election_key}_{field_end.isoformat()}_{slug(pollster)}_{race}_{slug(scope)}"
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
            "sample_size": to_sample(row.iloc[cols["sample"]]) if cols["sample"] is not None else None,
            "method": None,
            "population": "adult",
            "type": election_cfg["type"],
            "race": race,
            "race_type": race_type,
            "scope": scope,
            "scope_type": scope_type,
            "results": results,
            "source_url": source_url,
            "source_page": "tr.wikipedia.org",
            "source_date_text": str(date_text).strip(),
            "source_pollster_text": str(row.iloc[cols["pollster"]]).strip(),
            "status": "published",
        })
    return polls


def parse_national(election_key: str, election_cfg: dict, html: str, party_map, candidate_map, used_ids):
    polls: list[dict] = []
    for race, race_cfg in election_cfg["races"].items():
        allowed = set(race_cfg["entities"])
        for df in read_tables(html):
            polls.extend(parse_table(
                df,
                election_key=election_key,
                election_cfg=election_cfg,
                race=race,
                race_entities=allowed,
                scope="national",
                scope_type="national",
                race_type=None,
                source_url=election_cfg["source_url"],
                party_map=party_map,
                candidate_map=candidate_map,
                used_ids=used_ids,
            ))
    return dedupe(polls)


REGIONS = {
    "marmara", "ege", "ic anadolu", "akdeniz", "karadeniz",
    "dogu anadolu", "guneydogu anadolu",
}


def parse_local(election_key: str, election_cfg: dict, html: str, party_map, used_ids):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    polls: list[dict] = []
    region = None
    province = None
    district = None
    for node in soup.find_all(["h2", "h3", "h4", "table"]):
        if node.name in {"h2", "h3", "h4"}:
            text = node.get_text(" ", strip=True)
            text = re.sub(r"\[(?:değiştir|edit)\]", "", text).strip()
            if not text:
                continue
            if node.name == "h2":
                region = text
                province = None
                district = None
            elif node.name == "h3":
                province = text
                district = None
            else:
                district = text
            continue

        if district:
            scope = f"{province}/{district}" if province else district
            scope_type = "district"
            race_type = parse_scope(district) or "district_mayor"
        elif province:
            scope = province
            scope_type = "city"
            race_type = parse_scope(province) or "metropolitan_mayor"
        elif region:
            scope = region
            scope_norm = norm(region)
            if any(word in scope_norm for word in ("genel", "turkiye", "ulke", "ülke", "anketler")):
                scope = "national"
                scope_type = "national"
            elif scope_norm in REGIONS:
                scope_type = "region"
            else:
                scope_type = "city"
            race_type = parse_scope(region) or (
                "local_other" if scope_type in {"national", "region"} else "metropolitan_mayor"
            )
        else:
            scope = "national"
            scope_type = "national"
            race_type = "local_other"

        try:
            tables = pd.read_html(io.StringIO(str(node)), header=None, decimal=",", thousands=None)
        except ValueError:
            continue
        for df in tables:
            polls.extend(parse_table(
                df,
                election_key=election_key,
                election_cfg=election_cfg,
                race=race_type,
                race_entities=None,
                scope=scope,
                scope_type=scope_type,
                race_type=race_type,
                source_url=election_cfg["source_url"],
                party_map=party_map,
                candidate_map=AliasMap({}),
                used_ids=used_ids,
            ))
    return dedupe(polls)


def convert_existing(election_key: str, election_cfg: dict, party_map, candidate_map, used_ids):
    path = ROOT / election_cfg["use_existing"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    polls = []
    for poll in payload["polls"]:
        race = "parliamentary" if poll["type"] == "parliamentary" else (
            "presidential_runoff" if poll.get("round") == 2 else "presidential_first"
        )
        race_cfg = election_cfg["races"][race]
        allowed = set(race_cfg["entities"])
        mapping = {
            "P9": "AKP", "P21": "CHP", "P11": "MHP", "P22": "IYI",
            "P12": "HDP_DEM", "P10": "YRP", "P13": "TIP", "P24": "ZP",
            "P8": "BBP", "MP": "OTHER", "OTHER": "OTHER",
            "A": "ERDOGAN", "B": "KILICDAROGLU", "C": "OGAN", "D": "INCE",
        }
        results = {}
        for key, value in poll["results"].items():
            if value is None:
                continue
            entity = mapping.get(key, "OTHER")
            if entity not in allowed:
                entity = "OTHER"
            results[entity] = results.get(entity, 0.0) + value
        if len(results) < 2:
            continue
        pollster = canonical_pollster(clean_pollster(poll["pollster"]))
        base_id = f"{election_key}_{poll['field_end']}_{slug(pollster)}_{race}_national"
        poll_id = base_id
        suffix = 2
        while poll_id in used_ids:
            poll_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(poll_id)
        polls.append({
            **poll,
            "poll_id": poll_id,
            "legacy_poll_id": poll["poll_id"],
            "pollster": pollster,
            "type": election_cfg["type"],
            "race": race,
            "race_type": race,
            "scope": "national",
            "scope_type": "national",
            "results": results,
        })
    return dedupe(polls)


def dedupe(polls: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for poll in polls:
        key = (poll["race"], poll["scope"], norm(poll["pollster"]), poll["field_end"])
        current = best.get(key)
        if current is None or len(poll["results"]) > len(current["results"]):
            best[key] = poll
    return sorted(best.values(), key=lambda p: (p["field_end"], p["pollster"]))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if "polls" in payload:
        print(f"wrote {path.relative_to(ROOT)} ({len(payload['polls'])} polls)")
    else:
        print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    global POLLSTER_MAP
    elections = load_yaml("elections.yaml")["elections"]
    entities_cfg = load_yaml("entities.yaml")
    pollsters_cfg = load_yaml("pollsters.yaml")["pollsters"]
    POLLSTER_MAP = AliasMap({key: [key, *value] for key, value in pollsters_cfg.items()})
    party_map, candidate_map = build_entities(entities_cfg)

    only = set(sys.argv[1:])
    coverage = {}
    for election_key, election_cfg in elections.items():
        if only and election_key not in only:
            continue
        used_ids: set[str] = set()
        if election_cfg.get("use_existing"):
            polls = convert_existing(election_key, election_cfg, party_map, candidate_map, used_ids)
        else:
            print(f"fetching {election_key}: {election_cfg['source_url']}")
            html = fetch(election_cfg["source_url"])
            if election_cfg["type"] == "local":
                polls = parse_local(election_key, election_cfg, html, party_map, used_ids)
            else:
                polls = parse_national(election_key, election_cfg, html, party_map, candidate_map, used_ids)

        payload = {
            "meta": {
                "election_id": election_key,
                "election_type": election_cfg["type"],
                "date": election_cfg["date"],
                "runoff_date": election_cfg.get("runoff_date"),
                "source_url": election_cfg["source_url"],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "unit": "fraction",
                "coverage": "Wikipedia historical polling tables",
            },
            "polls": polls,
        }
        write_json(OUT / f"{election_key}.json", payload)
        by_race = {}
        for poll in polls:
            by_race.setdefault(poll["race"], []).append(poll)
        coverage[election_key] = {
            "total": len(polls),
            "by_race": {race: len(items) for race, items in by_race.items()},
            "scopes": sorted({p["scope"] for p in polls if p["scope_type"] == "city"}),
        }

    if coverage:
        write_json(OUT / "coverage.json", {"elections": coverage})


if __name__ == "__main__":
    main()
