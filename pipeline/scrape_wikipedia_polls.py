"""Scrape Turkish Wikipedia's 2023 election poll tables.

    uv run --with lxml --with beautifulsoup4 --with html5lib python pipeline/scrape_wikipedia_polls.py

Outputs:
  polls/2023_president.json
  polls/2023_parliament.json

Scope: the post-calendar (10 March 2023 onward) first-round, runoff and
parliamentary tables. The pre-calendar hypothetical-candidate tables are not
included in v1.
"""

from __future__ import annotations

import calendar
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

PRESIDENT_URL = (
    "https://tr.wikipedia.org/wiki/"
    "2023_T%C3%BCrkiye_cumhurba%C5%9Fkanl%C4%B1%C4%9F%C4%B1_se%C3%A7imi_"
    "i%C3%A7in_yap%C4%B1lan_anketler"
)
PARLIAMENT_URL = (
    "https://tr.wikipedia.org/wiki/"
    "%C3%9Clke_%C3%A7ap%C4%B1nda_2023_T%C3%BCrkiye_genel_se%C3%A7imleri_"
    "i%C3%A7in_yap%C4%B1lan_anketler"
)
OUT = Path("polls")

MONTHS = {
    "ocak": 1,
    "oca": 1,
    "şubat": 2,
    "subat": 2,
    "şub": 2,
    "sub": 2,
    "mart": 3,
    "mar": 3,
    "nisan": 4,
    "nis": 4,
    "mayıs": 5,
    "mayis": 5,
    "may": 5,
    "haziran": 6,
    "haz": 6,
    "temmuz": 7,
    "tem": 7,
    "ağustos": 8,
    "agustos": 8,
    "ağu": 8,
    "agu": 8,
    "eylül": 9,
    "eylul": 9,
    "eyl": 9,
    "ekim": 10,
    "eki": 10,
    "kasım": 11,
    "kasim": 11,
    "kas": 11,
    "aralık": 12,
    "aralik": 12,
    "ara": 12,
}
EXCLUDE_WORDS = [
    "ortalama",
    "seçim",
    "secim",
    "açıkladı",
    "acikladi",
    "çekildi",
    "ceklidi",
    "edildi",
    "oldu",
    "kuruldu",
    "ilan",
    "deprem",
    "vefat",
    "hayatını",
    "istifa",
]


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def read_tables(html: str) -> list[pd.DataFrame]:
    import io

    return pd.read_html(
        io.StringIO(html), header=None, decimal=",", thousands="."
    )


def is_nan(value) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def to_num(value) -> float | None:
    if value is None or is_nan(value):
        return None
    text = re.sub(r"\[[^\]]*\]", "", str(value)).strip()
    if text in {"–", "-", "—", ""}:
        return None
    text = text.replace("%", "").replace(" ", "")
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
    text = text.replace(".", "").replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def clean_pollster(value) -> str:
    text = re.sub(r"\[[^\]]*\]", "", str(value))
    return re.sub(r"\s+", " ", text).strip()


def month_number(token: str) -> int | None:
    token = token.lower().replace("i̇", "i")
    for key, value in MONTHS.items():
        if token.startswith(key):
            return value
    return None


def parse_date(text: str, default_year: int = 2023):
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
            end_day = 14 if month == 5 else last
            return date(year, month, 1), date(year, month, end_day), "month"

    return None


def slug(value: str) -> str:
    value = value.lower()
    value = (
        value.replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("â", "a")
    )
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "poll"


def should_skip(pollster: str, results: dict) -> bool:
    if not pollster:
        return True
    if any(word in pollster.lower() for word in EXCLUDE_WORDS):
        return True
    if not any(value is not None for value in results.values()):
        return True
    return False


def poll_record(
    *,
    date_text,
    pollster_text,
    sample_text,
    results,
    poll_type,
    round_number,
    source_url,
    used_ids,
):
    parsed = parse_date(date_text)
    if not parsed:
        return None
    start, end, precision = parsed
    pollster = clean_pollster(pollster_text)
    results = {key: (value / 100 if value is not None else None) for key, value in results.items()}
    if should_skip(pollster, results):
        return None

    base_id = f"{end.isoformat()}_{slug(pollster)}_{poll_type}"
    if round_number:
        base_id += f"_r{round_number}"
    poll_id = base_id
    suffix = 2
    while poll_id in used_ids:
        poll_id = f"{base_id}_{suffix}"
        suffix += 1
    used_ids.add(poll_id)

    return {
        "poll_id": poll_id,
        "pollster": pollster,
        "field_start": start.isoformat(),
        "field_end": end.isoformat(),
        "date_precision": precision,
        "sample_size": to_sample(sample_text),
        "method": None,
        "population": "adult",
        "type": poll_type,
        "round": round_number,
        "results": results,
        "undecided": None,
        "source_url": source_url,
        "source_page": "tr.wikipedia.org",
        "source_date_text": str(date_text).strip(),
        "source_pollster_text": str(pollster_text).strip(),
        "status": "published",
        "notes": None,
    }


def parse_presidential(tables: list[pd.DataFrame], source_url: str, used_ids: set) -> list[dict]:
    polls = []
    first = tables[0]
    if first.shape[1] < 7:
        raise SystemExit("unexpected presidential first-round table shape")
    for _, row in first.iloc[3:].iterrows():
        results = {
            "A": to_num(row.iloc[3]),
            "B": to_num(row.iloc[5]),
            "C": to_num(row.iloc[6]),
            "D": to_num(row.iloc[4]),
        }
        record = poll_record(
            date_text=row.iloc[0],
            pollster_text=row.iloc[1],
            sample_text=row.iloc[2],
            results=results,
            poll_type="presidential",
            round_number=1,
            source_url=source_url,
            used_ids=used_ids,
        )
        if record:
            polls.append(record)

    runoff = tables[1]
    if runoff.shape[1] < 5:
        raise SystemExit("unexpected presidential runoff table shape")
    for _, row in runoff.iloc[3:].iterrows():
        results = {
            "A": to_num(row.iloc[3]),
            "B": to_num(row.iloc[4]),
        }
        record = poll_record(
            date_text=row.iloc[0],
            pollster_text=row.iloc[1],
            sample_text=row.iloc[2],
            results=results,
            poll_type="presidential",
            round_number=2,
            source_url=source_url,
            used_ids=used_ids,
        )
        if record:
            polls.append(record)
    return polls


def parse_parliament(tables: list[pd.DataFrame], source_url: str, used_ids: set) -> list[dict]:
    table = tables[0]
    if table.shape[1] < 17:
        raise SystemExit("unexpected parliamentary table shape")
    polls = []
    for _, row in table.iloc[3:].iterrows():
        results = {
            "P9": to_num(row.iloc[3]),
            "P11": to_num(row.iloc[4]),
            "P8": to_num(row.iloc[5]),
            "P10": to_num(row.iloc[6]),
            "P21": to_num(row.iloc[8]),
            "P22": to_num(row.iloc[9]),
            "P12": to_num(row.iloc[11]),
            "P13": to_num(row.iloc[12]),
            "P24": to_num(row.iloc[14]),
            "MP": to_num(row.iloc[15]),
            "OTHER": to_num(row.iloc[16]),
        }
        record = poll_record(
            date_text=row.iloc[0],
            pollster_text=row.iloc[1],
            sample_text=row.iloc[2],
            results=results,
            poll_type="parliamentary",
            round_number=None,
            source_url=source_url,
            used_ids=used_ids,
        )
        if record:
            polls.append(record)
    return polls


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {path} ({len(payload['polls'])} polls)")


def main() -> None:
    used_ids: set[str] = set()
    president_tables = read_tables(fetch(PRESIDENT_URL))
    parliament_tables = read_tables(fetch(PARLIAMENT_URL))
    president_polls = parse_presidential(president_tables, PRESIDENT_URL, used_ids)
    parliament_polls = parse_parliament(parliament_tables, PARLIAMENT_URL, used_ids)

    now = datetime.now(timezone.utc).isoformat()
    write_json(
        OUT / "2023_president.json",
        {
            "meta": {
                "source": "Turkish Wikipedia",
                "source_url": PRESIDENT_URL,
                "scraped_at": now,
                "coverage": "2023 post-calendar first round and runoff",
                "unit": "fraction",
                "candidates": {"A": "Erdoğan", "B": "Kılıçdaroğlu", "C": "Oğan", "D": "İnce"},
            },
            "polls": president_polls,
        },
    )
    write_json(
        OUT / "2023_parliament.json",
        {
            "meta": {
                "source": "Turkish Wikipedia",
                "source_url": PARLIAMENT_URL,
                "scraped_at": now,
                "coverage": "2023 post-calendar parliamentary polls",
                "unit": "fraction",
            },
            "polls": parliament_polls,
        },
    )


if __name__ == "__main__":
    main()
