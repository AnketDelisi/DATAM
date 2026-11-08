"""Experimental two-layer proportional house-effect model.

Layer 1 estimates bloc-level relative bias. Layer 2 estimates within-bloc party
composition bias. Both are proportional deviations from the leave-one-pollster-
out consensus, then shrunk toward zero.

    python pipeline/house_effects_proportional.py

This is an experiment, not the production house-effect export.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from pipeline.house_effects import (
    Model,
    REFERENCE_BLOC,
    aggregate,
    apply_poll_effects,
    load_polls,
    load_yaml,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "analysis" / "house_effects_proportional.md"
TRAIN_ELECTIONS = {
    "2015-06", "2015-11", "2017-ref", "2018-general", "2018-pres", "2019-local",
}
MAX_RELATIVE = 0.75


def shrink(mean: float, effective_n: float, prior: float) -> float:
    value = mean * effective_n / (effective_n + prior)
    return max(-MAX_RELATIVE, min(MAX_RELATIVE, value))


def fit_proportional(model: Model) -> dict:
    bloc_records = defaultdict(lambda: defaultdict(list))
    party_records = defaultdict(lambda: defaultdict(list))
    pollsters = defaultdict(list)

    for poll in model.polls:
        parties = model.party_shares(poll)
        if not parties:
            continue
        blocs = model.bloc_shares(parties)
        ref_p = blocs.get(REFERENCE_BLOC, 0.0)
        consensus = model.consensus(poll)
        if ref_p <= 0 or not consensus:
            continue
        consensus_parties, consensus_blocs = consensus
        ref_c = consensus_blocs.get(REFERENCE_BLOC, 0.0)
        if ref_c <= 0:
            continue
        weight = model.poll_weight(poll)
        pollsters[poll["pollster"]].append(poll)
        pollster = poll["pollster"]

        for bloc in model.blocs:
            if bloc == REFERENCE_BLOC or bloc == "OTHER":
                continue
            p = blocs.get(bloc, 0.0)
            c = consensus_blocs.get(bloc, 0.0)
            if p <= 0 or c <= 0:
                continue
            relative = (p / ref_p) / (c / ref_c) - 1
            entity_weight = weight * (min(p, c) ** 0.5 + 1e-4)
            bloc_records[pollster][bloc].append((relative, entity_weight))

        if poll["type"] == "local":
            continue
        for bloc in model.blocs:
            keys = [
                key for key in parties
                if model.bloc_of.get(key) == bloc
                and key in consensus_parties
                and parties[key] > 0 and consensus_parties[key] > 0
            ]
            if len(keys) < 2:
                continue
            p_total = sum(parties[key] for key in keys)
            c_total = sum(consensus_parties[key] for key in keys)
            if p_total <= 0 or c_total <= 0:
                continue
            for key in keys:
                relative = (
                    (parties[key] / p_total)
                    / (consensus_parties[key] / c_total)
                    - 1
                )
                entity_weight = weight * (min(parties[key], consensus_parties[key]) ** 0.5 + 1e-4)
                party_records[pollster][key].append((relative, entity_weight))

    effects = {}
    for pollster in pollsters:
        bloc_effects = {REFERENCE_BLOC: 0.0}
        for bloc, values in bloc_records.get(pollster, {}).items():
            total = sum(weight for _, weight in values)
            if total <= 0:
                continue
            mean = sum(value * weight for value, weight in values) / total
            effective = total ** 2 / sum(weight ** 2 for _, weight in values)
            if effective < model.min_effective:
                continue
            bloc_effects[bloc] = shrink(mean, effective, model.shrink_prior)

        party_effects = {}
        for key, values in party_records.get(pollster, {}).items():
            total = sum(weight for _, weight in values)
            if total <= 0:
                continue
            mean = sum(value * weight for value, weight in values) / total
            effective = total ** 2 / sum(weight ** 2 for _, weight in values)
            if effective < model.min_effective:
                continue
            party_effects[key] = shrink(mean, effective, model.shrink_prior)

        for bloc in model.blocs:
            members = [key for key in party_effects if model.bloc_of.get(key) == bloc]
            if len(members) < 2:
                for key in members:
                    party_effects[key] = 0.0
                continue
            center = sum(party_effects[key] for key in members) / len(members)
            for key in members:
                party_effects[key] = max(-MAX_RELATIVE, min(MAX_RELATIVE, party_effects[key] - center))

        effects[pollster] = {
            "bloc_effects": bloc_effects,
            "party_effects": party_effects,
        }
    return effects


def apply_proportional_effect(shares: dict[str, float], effect: dict, bloc_of: dict) -> dict[str, float]:
    bloc_effects = effect.get("bloc_effects", {})
    party_effects = effect.get("party_effects", {})
    adjusted = {}
    for key, value in shares.items():
        factor = 1 / (1 + bloc_effects.get(bloc_of.get(key, "OTHER"), 0.0))
        adjusted[key] = value * factor
    adjusted = normalize(adjusted)
    groups = defaultdict(list)
    for key in adjusted:
        groups[bloc_of.get(key, "OTHER")].append(key)
    for keys in groups.values():
        before = sum(adjusted[key] for key in keys)
        if before <= 0:
            continue
        for key in keys:
            adjusted[key] *= 1 / (1 + party_effects.get(key, 0.0))
        after = sum(adjusted[key] for key in keys)
        if after > 0:
            for key in keys:
                adjusted[key] *= before / after
    return normalize(adjusted)


def normalize(values: dict[str, float]) -> dict[str, float]:
    clean = {key: value for key, value in values.items() if value and value > 0}
    total = sum(clean.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in clean.items()}


def apply_to_poll(poll: dict, effects: dict, bloc_of: dict) -> dict:
    effect = effects.get(poll["pollster"])
    if not effect:
        return poll
    shares = normalize({
        key: value for key, value in poll.get("results", {}).items()
        if value is not None and value > 0
    })
    if not shares:
        return poll
    return {**poll, "results": apply_proportional_effect(shares, effect, bloc_of)}


def evaluate(train: list[dict], test: list[dict], entities_cfg: dict, he_cfg: dict):
    elections = load_yaml("elections.yaml")["elections"]
    model = Model(train, entities_cfg, he_cfg, date.fromisoformat("2023-05-14"))
    proportional = fit_proportional(model)
    log = model.fit()

    results = {}
    for election_id, race, label in [
        ("2023-general", "parliamentary", "parliament"),
        ("2023-pres", "presidential_first", "president_first"),
    ]:
        actual = elections[election_id]["races"][race]["actual"]
        polls = [
            poll for poll in test
            if poll["election_id"] == election_id and poll["race"] == race
        ]
        cutoff = elections[election_id]["date"]
        baseline = aggregate(polls, list(actual), cutoff=cutoff)
        log_polls = [
            apply_poll_effects(poll, log, model.bloc_of) for poll in polls
        ]
        prop_polls = [
            apply_to_poll(poll, proportional, model.bloc_of) for poll in polls
        ]
        log_agg = aggregate(log_polls, list(actual), cutoff=cutoff)
        prop_agg = aggregate(prop_polls, list(actual), cutoff=cutoff)

        def mae(values):
            errors = [
                abs(values[key] - actual[key])
                for key in actual
                if key in values and values[key] is not None
            ]
            return sum(errors) / len(errors) if errors else None

        results[label] = {
            "n_polls": len(polls),
            "baseline": mae(baseline),
            "log": mae(log_agg),
            "proportional": mae(prop_agg),
            "rows": [
                {
                    "entity": key,
                    "actual": actual[key],
                    "baseline": baseline.get(key),
                    "log": log_agg.get(key),
                    "proportional": prop_agg.get(key),
                }
                for key in actual
            ],
        }
    return results


def main() -> None:
    polls = load_polls()
    train = [poll for poll in polls if poll["election_id"] in TRAIN_ELECTIONS]
    results = evaluate(train, polls, load_yaml("entities.yaml"), load_yaml("house_effects.yaml"))
    lines = [
        "# Two-layer proportional house effects — experiment",
        "",
        "Bloc effects are proportional relative odds versus the leave-one-pollster-out consensus.",
        "Party effects are proportional within-bloc composition residuals. Effects are shrunk.",
        "",
    ]
    for label, result in results.items():
        lines += [
            f"## {label}",
            "",
            f"Polls: {result['n_polls']}",
            "",
            "| model | MAE |",
            "|---|---:|",
            f"| raw average | {result['baseline']:.5f} |",
            f"| two-layer log | {result['log']:.5f} |",
            f"| two-layer proportional | {result['proportional']:.5f} |",
            "",
        ]
    lines += [
        "## Conclusion",
        "",
        "The proportional variant is not a clear improvement. It is slightly better",
        "than the log model for the presidential race but worse for parliament, and",
        "neither beats the raw average. Because log-ratio and relative-proportional",
        "effects are nearly equivalent for small biases, the limiting factor is the",
        "signal in historical pollster behaviour, not the link function.",
        "",
        "Keep this as an experiment; do not promote it to the production export",
        "unless a later validation run shows a consistent gain in both races.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for label, result in results.items():
        print(label, "baseline", round(result["baseline"], 5),
              "log", round(result["log"], 5),
              "proportional", round(result["proportional"], 5))


if __name__ == "__main__":
    main()
