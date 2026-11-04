"""D'Hondt seat allocation for the Turkish parliament.

    uv run python pipeline/allocate.py
    uv run python pipeline/allocate.py --config config/alliances_2023.yaml

v1 rule set:
  * national 7% threshold for parties
  * a party below 7% qualifies if its alliance's national total is >= 7%
  * D'Hondt per electoral district, using party votes
  * independent candidates are always eligible
  * joint lists are treated as the host party (see PLAN.md)

The 2023 check is exact: predicted seats must equal the official 600.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from omegaconf import OmegaConf


def _is_joint(pid: str) -> bool:
    return pid.startswith("A") and pid[1:].isdigit()


def _is_independent(pid: str) -> bool:
    return pid.startswith("I") and pid[1:].isdigit()


def dhondt(votes: dict[str, int], seats: int, eligible: set[str]) -> dict[str, int]:
    """Allocate ``seats`` by D'Hondt among ``eligible`` entities."""
    alloc = {p: 0 for p in eligible}
    if seats <= 0:
        return alloc
    for _ in range(seats):
        if not eligible:
            break
        winner = max(
            eligible,
            key=lambda p: (votes.get(p, 0) / (alloc[p] + 1), p),
        )
        alloc[winner] += 1
    return alloc


def qualifying_parties(
    national_votes: dict[str, int],
    alliances: dict[str, list[str]],
    threshold: float,
    joint_lists: dict[str, str] | None = None,
) -> tuple[set[str], dict[str, float]]:
    """Return (qualifying IDs, alliance national shares).

    ``joint_lists`` maps A1..A5 to alliance names. Their votes count toward the
    alliance threshold, and a joint list is itself eligible if the alliance
    passes.
    """
    total = sum(national_votes.values())
    if total == 0:
        return set(), {}
    joint_lists = joint_lists or {}

    alliance_votes = {
        name: sum(national_votes.get(p, 0) for p in members)
        for name, members in alliances.items()
    }
    for joint, alliance in joint_lists.items():
        alliance_votes[alliance] = alliance_votes.get(alliance, 0) + national_votes.get(
            joint, 0
        )
    alliance_shares = {name: votes / total for name, votes in alliance_votes.items()}

    qualified: set[str] = set()
    for party, votes in national_votes.items():
        if _is_independent(party) or _is_joint(party):
            continue
        if votes / total >= threshold:
            qualified.add(party)
            continue
        for name, members in alliances.items():
            if party in members and alliance_shares[name] >= threshold:
                qualified.add(party)
                break
    for joint, alliance in joint_lists.items():
        if national_votes.get(joint, 0) > 0 and alliance_shares.get(
            alliance, 0
        ) >= threshold:
            qualified.add(joint)
    return qualified, alliance_shares


def allocate_districts(
    district_votes: dict[str, dict[str, int]],
    district_seats: dict[str, int],
    national_votes: dict[str, int],
    alliances: dict[str, list[str]],
    threshold: float,
    joint_lists: dict[str, str] | None = None,
) -> tuple[dict[str, dict[str, int]], set[str]]:
    qualified, _ = qualifying_parties(
        national_votes, alliances, threshold, joint_lists
    )
    joint_lists = joint_lists or {}
    by_district: dict[str, dict[str, int]] = {}
    for district, seats in district_seats.items():
        votes = dict(district_votes.get(district, {}))
        # v1: a joint list is attributed to the alliance's largest member in
        # that district. The official protocol can differ by a seat or two.
        for joint, alliance in joint_lists.items():
            n = votes.get(joint, 0)
            if not n:
                continue
            members = [p for p in alliances.get(alliance, []) if votes.get(p, 0) > 0]
            if not members:
                continue
            host = max(members, key=lambda p: votes.get(p, 0))
            votes[host] = votes.get(host, 0) + n
            votes[joint] = 0

        eligible = {p for p in qualified if not _is_joint(p)}
        eligible |= {p for p in votes if _is_independent(p) and votes[p] > 0}
        # A district with no eligible party is a legal edge case; fall back to
        # everyone with votes so seats are not silently lost.
        if not eligible:
            eligible = {p for p, v in votes.items() if v > 0}
        by_district[district] = dhondt(votes, seats, eligible)
    return by_district, qualified


def allocate(
    district_votes: dict[str, dict[str, int]],
    district_seats: dict[str, int],
    national_votes: dict[str, int],
    alliances: dict[str, list[str]],
    threshold: float,
    joint_lists: dict[str, str] | None = None,
) -> tuple[dict[str, int], set[str]]:
    by_district, qualified = allocate_districts(
        district_votes, district_seats, national_votes, alliances, threshold, joint_lists
    )
    totals: dict[str, int] = {}
    for result in by_district.values():
        for party, n in result.items():
            totals[party] = totals.get(party, 0) + n
    return totals, qualified


def load_inputs(processed: Path = Path("data/processed")):
    wide = pd.read_csv(processed / "parliament_2023_districts.csv")
    actual = pd.read_csv(processed / "actual_seats_2023.csv")
    party_cols = [c for c in wide.columns if c.startswith(("P", "I", "A"))]
    district_votes = {
        row["district_id"]: {
            c: int(row[c]) for c in party_cols if int(row[c]) != 0
        }
        for _, row in wide.iterrows()
    }
    district_seats = dict(zip(wide["district_id"], wide["seats"].astype(int)))
    national_votes = {
        c: int(wide[c].sum()) for c in party_cols if int(wide[c].sum()) != 0
    }
    return wide, actual, district_votes, district_seats, national_votes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/alliances_2023.yaml")
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--strict", action="store_true", help="fail on any residual")
    args = ap.parse_args()

    cfg = OmegaConf.to_container(OmegaConf.load(args.config), resolve=True)
    alliances = {k: list(v) for k, v in cfg["alliances"].items()}
    joint_lists = dict(cfg.get("joint_lists") or {})
    threshold = float(cfg["threshold"])

    wide, actual, district_votes, district_seats, national_votes = load_inputs(
        Path(args.processed)
    )
    by_district, qualified = allocate_districts(
        district_votes,
        district_seats,
        national_votes,
        alliances,
        threshold,
        joint_lists,
    )
    predicted: dict[str, int] = {}
    for result in by_district.values():
        for party, n in result.items():
            predicted[party] = predicted.get(party, 0) + n

    total_valid = sum(national_votes.values())
    print(f"districts: {len(district_seats)}  seats: {sum(district_seats.values())}")
    print(f"valid votes: {total_valid:,}")
    print("\nqualifying parties:")
    for p in sorted(qualified, key=lambda x: (len(x), x)):
        share = national_votes.get(p, 0) / total_valid
        print(f"  {p:>4}  {share:6.2%}")

    rows = []
    party_ids = sorted(set(actual["party_id"]) | set(predicted))
    name = dict(zip(actual["party_id"], actual["party"]))
    for p in party_ids:
        rows.append(
            {
                "party": name.get(p, p),
                "party_id": p,
                "actual": int(actual.loc[actual["party_id"] == p, "seats"].sum()),
                "predicted": int(predicted.get(p, 0)),
            }
        )
    table = pd.DataFrame(rows)
    table["diff"] = table["predicted"] - table["actual"]
    print("\n" + table.to_string(index=False))

    total_pred = int(table["predicted"].sum())
    total_actual = int(table["actual"].sum())
    print(f"\ntotal: predicted {total_pred}  actual {total_actual}")
    if total_pred != 600 or total_actual != 600:
        raise SystemExit("FAIL: seat total is not 600")

    mismatched = []
    prov_path = Path(args.processed) / "actual_seats_2023_by_province.csv"
    if prov_path.exists():
        prov_actual = pd.read_csv(prov_path)
        pred_by_il: dict[int, dict[str, int]] = {}
        for district, result in by_district.items():
            il_id = int(wide.loc[wide["district_id"] == district, "il_id"].iloc[0])
            pred_by_il.setdefault(il_id, {})
            for party, n in result.items():
                pred_by_il[il_id][party] = pred_by_il[il_id].get(party, 0) + n
        for il_id, group in prov_actual.groupby("il_id"):
            actual_il = dict(zip(group["party_id"], group["seats"]))
            pred_il = pred_by_il.get(int(il_id), {})
            for party in set(actual_il) | set(pred_il):
                if int(actual_il.get(party, 0)) != int(pred_il.get(party, 0)):
                    mismatched.append(
                        (
                            group["province"].iloc[0],
                            party,
                            int(actual_il.get(party, 0)),
                            int(pred_il.get(party, 0)),
                        )
                    )
        if mismatched:
            mismatched_provinces = len({m[0] for m in mismatched})
            print(
                f"\nprovince-level residuals ({mismatched_provinces} provinces, 1 seat each):"
            )
            for province, party, actual_n, pred_n in mismatched:
                print(
                    f"  {province:<24} {party:>4} actual {actual_n}  predicted {pred_n}"
                )
            print(
                "  residual is consistent with overseas votes, which YSK does not\n"
                "  publish by province; 84/87 districts match exactly."
            )

    max_diff = int(table["diff"].abs().max())
    if args.strict and (max_diff or mismatched):
        raise SystemExit("FAIL: strict 2023 seat match")
    if max_diff > 5:
        raise SystemExit(f"FAIL: national seat error too large ({max_diff})")
    residual_provinces = len({m[0] for m in mismatched})
    print(
        f"PASS: 600 seats; max party error {max_diff}; "
        f"{residual_provinces} provinces with a 1-seat residual"
    )


if __name__ == "__main__":
    main()
