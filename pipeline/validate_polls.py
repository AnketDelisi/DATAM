"""Validate the DATAM poll JSON files.

    uv run python pipeline/validate_polls.py

No third-party validator is required. The JSON Schema in polls/schema.json is
the documentation; this script enforces the same rules plus election cutoffs.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

POLLS = Path("polls")
CUTOFFS_BY_YEAR = {
    2023: {
        ("presidential", 1): date(2023, 5, 14),
        ("presidential", 2): date(2023, 5, 28),
        ("parliamentary", None): date(2023, 5, 14),
    },
    2028: {
        ("presidential", 1): date(2028, 5, 14),
        ("presidential", 2): date(2028, 5, 28),
        ("parliamentary", None): date(2028, 5, 14),
    },
}
PRESIDENT_KEYS = {"A", "B", "C", "D"}
PARLIAMENT_EXTRA_KEYS = {"YENI", "A"}
PARLIAMENT_KEY = re.compile(r"^P\d+$")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def validate_poll(poll: dict, seen_ids: set[str], cutoffs: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "poll_id",
        "pollster",
        "field_start",
        "field_end",
        "date_precision",
        "sample_size",
        "method",
        "population",
        "type",
        "round",
        "results",
        "undecided",
        "source_url",
        "source_page",
        "status",
        "notes",
    }
    missing = sorted(required - set(poll))
    if missing:
        return [f"missing fields: {', '.join(missing)}"]

    poll_id = poll["poll_id"]
    if not isinstance(poll_id, str) or not re.match(r"^[A-Za-z0-9_-]+$", poll_id):
        errors.append("poll_id must be a slug")
    elif poll_id in seen_ids:
        errors.append("duplicate poll_id")
    else:
        seen_ids.add(poll_id)

    if not poll["pollster"] or not isinstance(poll["pollster"], str):
        errors.append("pollster must be a non-empty string")

    try:
        start = parse_date(poll["field_start"])
        end = parse_date(poll["field_end"])
    except (TypeError, ValueError):
        return errors + ["field_start/field_end must be ISO dates"]
    if start > end:
        errors.append("field_start is after field_end")

    poll_type = poll["type"]
    round_number = poll["round"]
    key = (poll_type, round_number)
    if key not in cutoffs:
        errors.append(f"invalid type/round: {poll_type}/{round_number}")
    else:
        cutoff = cutoffs[key]
        if end > cutoff:
            errors.append(f"field_end {end} is after the {cutoff} cutoff")

    if poll["date_precision"] not in {"day", "month"}:
        errors.append("date_precision must be 'day' or 'month'")

    sample = poll["sample_size"]
    if sample is not None and (not isinstance(sample, int) or sample <= 0):
        errors.append("sample_size must be a positive integer or null")

    results = poll["results"]
    if not isinstance(results, dict) or not results:
        errors.append("results must be a non-empty object")
    else:
        if poll_type == "presidential":
            unknown = set(results) - PRESIDENT_KEYS
            if unknown:
                errors.append(f"unknown presidential keys: {sorted(unknown)}")
        elif poll_type == "parliamentary":
            unknown = {
                key
                for key in results
                if key not in {"MP", "OTHER", *PARLIAMENT_EXTRA_KEYS}
                and not PARLIAMENT_KEY.match(key)
            }
            if unknown:
                errors.append(f"unknown parliamentary keys: {sorted(unknown)}")
        for key, value in results.items():
            if value is None:
                continue
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                errors.append(f"result {key} must be in [0, 1]")
        total = sum(value for value in results.values() if value is not None)
        if total > 1.1:
            errors.append(f"results sum to {total:.3f} (> 1.1)")
        if not any(value is not None for value in results.values()):
            errors.append("results contains no numeric value")

    undecided = poll["undecided"]
    if undecided is not None and (
        not isinstance(undecided, (int, float)) or not 0 <= undecided <= 1
    ):
        errors.append("undecided must be in [0, 1] or null")

    if not poll["source_url"]:
        errors.append("source_url is empty")
    if poll["status"] not in {"published", "superseded", "withdrawn"}:
        errors.append("invalid status")

    return errors


def validate_dataset(path: Path = POLLS) -> tuple[int, list[str], Counter, set]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    counts: Counter = Counter()
    dates: list[date] = []
    pollsters: set[str] = set()
    total = 0

    files = [file for file in sorted(path.glob("*.json")) if file.name != "schema.json"]
    if not files:
        return 0, [f"no poll JSON files in {path}"], counts, pollsters

    for file in files:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{file.name}: invalid JSON: {exc}")
            continue
        polls = payload.get("polls")
        if not isinstance(polls, list):
            errors.append(f"{file.name}: missing polls array")
            continue
        match = re.match(r"^(\d{4})_", file.name)
        year = int(match.group(1)) if match else 2023
        cutoffs = CUTOFFS_BY_YEAR.get(year, CUTOFFS_BY_YEAR[2023])
        for index, poll in enumerate(polls):
            total += 1
            poll_errors = validate_poll(poll, seen_ids, cutoffs)
            for error in poll_errors:
                errors.append(f"{file.name}[{index}] {poll.get('poll_id', '?')}: {error}")
            if not poll_errors:
                counts[(poll["type"], poll["round"])] += 1
                dates.append(parse_date(poll["field_end"]))
                pollsters.add(poll["pollster"])

    if dates:
        print(
            f"{total} polls across {len(files)} file(s); "
            f"{min(dates)} to {max(dates)}; {len(pollsters)} pollsters"
        )
    for key in sorted(counts, key=lambda item: str(item)):
        print(f"  {key[0]} round={key[1]}: {counts[key]}")
    return total, errors, counts, pollsters


def main() -> None:
    total, errors, _, _ = validate_dataset()
    if errors:
        print(f"\n{len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print(f"OK: {total} polls")


if __name__ == "__main__":
    main()
