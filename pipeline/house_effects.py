"""Estimate two-level pollster house effects from historical polls.

Level 1: bloc-level multiplicative bias relative to the leave-one-pollster-out
consensus in the same contest.  Level 2: within-bloc party composition bias,
which is independent of the bloc-level effect.

Outputs ``web/data/house_effects.json``.  Run:

    python pipeline/house_effects.py
    python pipeline/house_effects.py --backtest
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HISTORICAL = ROOT / "polls" / "historical"
CONFIG = ROOT / "config"
WEB_OUT = ROOT / "web" / "data" / "house_effects.json"
WEB_BACKTEST_OUT = ROOT / "web" / "data" / "house_effects_2019.json"
BACKTEST_OUT = HISTORICAL / "backtest_2023.json"
TRAIN_ELECTIONS = {
    "2015-06", "2015-11", "2017-ref",
    "2018-general", "2018-pres", "2019-local",
}

LOCAL_RACES = {
    "metropolitan_mayor", "district_mayor", "municipal_council",
    "provincial_council", "local_other", "mayor",
}
REFERENCE_BLOC = "INCUMBENT"
SKIP_BLOC_EFFECTS = {"OTHER"}
MAX_LOG_EFFECT = 0.7


def pollster_key(value: str) -> str:
    text = value.upper().replace("?", "I").replace("?", "S").replace("?", "G").replace("?", "C").replace("?", "O").replace("?", "U").replace("?", "A")
    return re.sub(r"[^A-Z0-9]", "", text)


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize(values: dict[str, float]) -> dict[str, float]:
    clean = {key: value for key, value in values.items() if value and value > 0}
    total = sum(clean.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in clean.items()}


def weighted_mean(values: list[tuple[float, float]]) -> tuple[float, float] | None:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return None
    mean = sum(value * weight for value, weight in values) / total_weight
    effective_n = total_weight ** 2 / sum(weight ** 2 for _, weight in values)
    return mean, effective_n


def clamp(value: float) -> float:
    return max(-MAX_LOG_EFFECT, min(MAX_LOG_EFFECT, value))


class Model:
    def __init__(self, polls: list[dict], entities_cfg: dict, he_cfg: dict, reference_date: date):
        self.polls = polls
        self.he_cfg = he_cfg
        self.reference_date = reference_date
        self.half_life = float(he_cfg.get("half_life_days", 1095))
        self.shrink_prior = float(he_cfg.get("shrink_prior_polls", 2))
        self.min_effective = float(he_cfg.get("min_effective_polls", 2))
        self.local_bloc_only = bool(he_cfg.get("local_bloc_only", True))
        self.election_weights = he_cfg.get("election_type_weights", {})
        self.race_weights = he_cfg.get("race_type_weights", {})
        self.correction_strength = he_cfg.get("correction_strength", {})
        self.correction_mode = he_cfg.get("correction_mode", {})

        self.bloc_of = {
            party_id: party["bloc"]
            for party_id, party in entities_cfg["parties"].items()
        }
        self.bloc_of.update({
            cand_id: cand["bloc"]
            for cand_id, cand in entities_cfg["candidates"].items()
        })
        self.blocs = sorted(set(self.bloc_of.values()))

        self.contest_polls: dict[tuple, list[dict]] = defaultdict(list)
        self.contest_pollster_means: dict[tuple, dict[str, dict[str, float]]] = defaultdict(dict)
        for poll in polls:
            contest = self.contest_key(poll)
            self.contest_polls[contest].append(poll)
        for contest, items in self.contest_polls.items():
            by_pollster: dict[str, list[dict[str, float]]] = defaultdict(list)
            for poll in items:
                shares = self.party_shares(poll)
                if shares:
                    by_pollster[poll["pollster"]].append(shares)
            for pollster, share_list in by_pollster.items():
                mean = {}
                for shares in share_list:
                    for key, value in shares.items():
                        mean[key] = mean.get(key, 0.0) + value
                for key in mean:
                    mean[key] /= len(share_list)
                self.contest_pollster_means[contest][pollster] = normalize(mean)

    @staticmethod
    def contest_key(poll: dict) -> tuple:
        return (poll["election_id"], poll["race"], poll["scope"])

    def party_shares(self, poll: dict) -> dict[str, float]:
        results = {}
        for key, value in poll.get("results", {}).items():
            if value is None or value <= 0:
                continue
            entity = key if key in self.bloc_of else "OTHER"
            results[entity] = results.get(entity, 0.0) + float(value)
        return normalize(results)

    def bloc_shares(self, party_shares: dict[str, float]) -> dict[str, float]:
        blocs = {}
        for key, value in party_shares.items():
            bloc = self.bloc_of.get(key, "OTHER")
            blocs[bloc] = blocs.get(bloc, 0.0) + value
        return normalize(blocs)

    def consensus(self, poll: dict) -> tuple[dict[str, float], dict[str, float]] | None:
        contest = self.contest_key(poll)
        others = {
            pollster: shares
            for pollster, shares in self.contest_pollster_means[contest].items()
            if pollster != poll["pollster"]
        }
        if not others:
            return None
        mean = {}
        for shares in others.values():
            for key, value in shares.items():
                mean[key] = mean.get(key, 0.0) + value / len(others)
        parties = normalize(mean)
        if not parties:
            return None
        return parties, self.bloc_shares(parties)

    def poll_weight(self, poll: dict) -> float:
        election_weight = float(self.election_weights.get(poll["type"], 1.0))
        race_key = poll.get("race_type") or poll.get("race")
        race_weight = float(self.race_weights.get(race_key, 1.0))
        age = (self.reference_date - date.fromisoformat(poll["field_end"])).days
        recency = 0.5 ** (max(0, age) / self.half_life)
        return election_weight * race_weight * recency

    def fit(self):
        bloc_records: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
        party_records: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
        pollster_polls: dict[str, list[dict]] = defaultdict(list)
        pollster_contests: dict[str, set] = defaultdict(set)

        for poll in self.polls:
            parties = self.party_shares(poll)
            if not parties:
                continue
            blocs = self.bloc_shares(parties)
            if blocs.get(REFERENCE_BLOC, 0.0) <= 0:
                continue
            consensus = self.consensus(poll)
            if not consensus:
                continue
            consensus_parties, consensus_blocs = consensus
            if consensus_blocs.get(REFERENCE_BLOC, 0.0) <= 0:
                continue

            weight = self.poll_weight(poll)
            pollster = poll["pollster"]
            pollster_polls[pollster].append(poll)
            pollster_contests[pollster].add(self.contest_key(poll))

            ref_p = blocs[REFERENCE_BLOC]
            ref_c = consensus_blocs[REFERENCE_BLOC]
            for bloc in self.blocs:
                if bloc == REFERENCE_BLOC or bloc in SKIP_BLOC_EFFECTS:
                    continue
                p = blocs.get(bloc, 0.0)
                c = consensus_blocs.get(bloc, 0.0)
                if p <= 0 or c <= 0:
                    continue
                diff = math.log(p / ref_p) - math.log(c / ref_c)
                entity_weight = weight * math.sqrt(min(p, c) + 1e-4)
                bloc_records[pollster][bloc].append((diff, entity_weight))

            if self.local_bloc_only and poll["type"] == "local":
                continue
            if poll.get("race_type") in LOCAL_RACES:
                continue

            for bloc in self.blocs:
                keys = [
                    key for key in parties
                    if self.bloc_of.get(key) == bloc
                    and key in consensus_parties
                    and parties[key] > 0
                    and consensus_parties[key] > 0
                ]
                if len(keys) < 2:
                    continue
                log_p = {key: math.log(parties[key]) for key in keys}
                log_c = {key: math.log(consensus_parties[key]) for key in keys}
                mean_p = sum(log_p.values()) / len(keys)
                mean_c = sum(log_c.values()) / len(keys)
                for key in keys:
                    diff = (log_p[key] - mean_p) - (log_c[key] - mean_c)
                    entity_weight = weight * math.sqrt(min(parties[key], consensus_parties[key]) + 1e-4)
                    party_records[pollster][key].append((diff, entity_weight))

        return self._finish(bloc_records, party_records, pollster_polls, pollster_contests)

    def _finish(self, bloc_records, party_records, pollster_polls, pollster_contests):
        output = {}
        all_pollsters = set(pollster_polls)
        for pollster in sorted(all_pollsters):
            bloc_effects = {REFERENCE_BLOC: 0.0}
            bloc_n = {}
            for bloc, values in bloc_records.get(pollster, {}).items():
                result = weighted_mean(values)
                if not result:
                    continue
                mean, effective_n = result
                if effective_n < self.min_effective:
                    continue
                shrink = effective_n / (effective_n + self.shrink_prior)
                bloc_effects[bloc] = clamp(mean * shrink)
                bloc_n[bloc] = round(effective_n, 2)

            party_effects = {}
            party_n = {}
            for key, values in party_records.get(pollster, {}).items():
                result = weighted_mean(values)
                if not result:
                    continue
                mean, effective_n = result
                if effective_n < self.min_effective:
                    continue
                shrink = effective_n / (effective_n + self.shrink_prior)
                party_effects[key] = clamp(mean * shrink)
                party_n[key] = round(effective_n, 2)

            for bloc in self.blocs:
                members = [key for key, value in party_effects.items() if self.bloc_of.get(key) == bloc]
                if len(members) < 2:
                    for key in members:
                        party_effects[key] = 0.0
                    continue
                center = sum(party_effects[key] for key in members) / len(members)
                for key in members:
                    party_effects[key] = clamp(party_effects[key] - center)

            total_effects = {}
            for key, bloc in self.bloc_of.items():
                if bloc in bloc_effects or key in party_effects:
                    total_effects[key] = bloc_effects.get(bloc, 0.0) + party_effects.get(key, 0.0)

            polls = pollster_polls[pollster]
            output[pollster] = {
                "n_polls": len(polls),
                "n_contests": len(pollster_contests[pollster]),
                "last_poll": max(poll["field_end"] for poll in polls),
                "bloc_effects": {key: round(value, 6) for key, value in bloc_effects.items()},
                "bloc_effective_n": bloc_n,
                "party_effects": {key: round(value, 6) for key, value in party_effects.items()},
                "party_effective_n": party_n,
                "total_effects": {key: round(value, 6) for key, value in total_effects.items()},
            }
        return output


def _pollster_mapping() -> dict[str, str]:
    cfg = load_yaml("pollsters.yaml")["pollsters"]
    mapping = {}
    for canonical, aliases in cfg.items():
        for alias in [canonical, *aliases]:
            mapping[pollster_key(str(alias))] = canonical
    return mapping


def load_polls() -> list[dict]:
    pollster_map = _pollster_mapping()
    polls = []
    for path in sorted(HISTORICAL.glob("*.json")):
        if path.name in {"coverage.json", "backtest_2023.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        for poll in payload.get("polls", []):
            poll = dict(poll)
            poll["election_id"] = meta.get("election_id", path.stem)
            poll["type"] = poll.get("type") or meta.get("election_type")
            poll["pollster"] = pollster_map.get(pollster_key(poll["pollster"]), poll["pollster"])
            if not poll.get("race_type"):
                poll["race_type"] = poll.get("race")
            polls.append(poll)
    return polls


def payload_for_web(effects: dict, polls: list[dict], model: Model,
                    one_level: dict | None = None,
                    hierarchical: dict | None = None) -> dict:
    if one_level is not None:
        for pollster, effect in effects.items():
            effect["one_level_effects"] = one_level.get(pollster, {})
    if hierarchical is not None:
        for pollster, effect in effects.items():
            effect["hierarchical_effects"] = hierarchical.get(pollster, {})
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "two-level log-ratio and one-level party effects; race-specific damping",
            "effect_sign": "log bias vs consensus; apply exp(-effect) to correct",
            "skipped_bloc_effects": sorted(SKIP_BLOC_EFFECTS),
            "reference_bloc": REFERENCE_BLOC,
            "half_life_days": model.half_life,
            "reference_date": model.reference_date.isoformat(),
            "min_effective_polls": model.min_effective,
            "shrink_prior_polls": model.shrink_prior,
            "local_bloc_only": model.local_bloc_only,
            "poll_count": len(polls),
            "pollster_count": len(effects),
            "bloc_of": model.bloc_of,
            "election_type_weights": model.election_weights,
            "race_type_weights": model.race_weights,
            "correction_strength": model.correction_strength,
            "correction_mode": model.correction_mode,
        },
        "pollsters": effects,
    }


def aggregate(polls: list[dict], entities: list[str], cutoff: str | None = None,
              half_life_days: float = 28) -> dict[str, float]:
    sums = defaultdict(float)
    weights = defaultdict(float)
    for poll in polls:
        if cutoff and poll["field_end"] > cutoff:
            continue
        shares = {}
        for key, value in poll.get("results", {}).items():
            if value is not None and value > 0:
                shares[key] = shares.get(key, 0.0) + value
        shares = normalize(shares)
        if not shares:
            continue
        age = (date.fromisoformat(cutoff) - date.fromisoformat(poll["field_end"])).days if cutoff else 0
        recency = 0.5 ** (max(0, age) / half_life_days)
        sample = poll.get("sample_size") or 1000
        weight = recency * math.sqrt(sample)
        for key in entities:
            if key in shares:
                sums[key] += shares[key] * weight
                weights[key] += weight
    result = {key: sums[key] / weights[key] for key in entities if weights[key] > 0}
    return normalize(result)


def apply_effect_set(shares: dict[str, float], effects: dict, bloc_of: dict) -> dict[str, float]:
    bloc_effects = effects.get("bloc_effects", {})
    party_effects = effects.get("party_effects", {})
    adjusted = {}
    for key, value in shares.items():
        bloc = bloc_of.get(key, "OTHER")
        adjusted[key] = value * math.exp(-bloc_effects.get(bloc, 0.0))
    adjusted = normalize(adjusted)

    by_bloc = defaultdict(list)
    for key in adjusted:
        by_bloc[bloc_of.get(key, "OTHER")].append(key)
    for keys in by_bloc.values():
        before = sum(adjusted[key] for key in keys)
        if before <= 0:
            continue
        for key in keys:
            adjusted[key] *= math.exp(-party_effects.get(key, 0.0))
        after = sum(adjusted[key] for key in keys)
        if after > 0:
            for key in keys:
                adjusted[key] *= before / after
    return normalize(adjusted)


def fit_one_level(model: Model) -> dict:
    records: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for poll in model.polls:
        parties = model.party_shares(poll)
        consensus = model.consensus(poll)
        if not parties or not consensus:
            continue
        consensus_parties = consensus[0]
        common = [
            key for key in parties
            if key in consensus_parties and parties[key] > 0 and consensus_parties[key] > 0
        ]
        if len(common) < 2:
            continue
        weight = model.poll_weight(poll)
        log_p = {key: math.log(parties[key]) for key in common}
        log_c = {key: math.log(consensus_parties[key]) for key in common}
        mean_p = sum(log_p.values()) / len(common)
        mean_c = sum(log_c.values()) / len(common)
        for key in common:
            diff = (log_p[key] - mean_p) - (log_c[key] - mean_c)
            entity_weight = weight * math.sqrt(min(parties[key], consensus_parties[key]) + 1e-4)
            records[poll["pollster"]][key].append((diff, entity_weight))

    output = {}
    for pollster, by_party in records.items():
        effects = {}
        for key, values in by_party.items():
            result = weighted_mean(values)
            if not result:
                continue
            mean, effective_n = result
            if effective_n < model.min_effective:
                continue
            shrink = effective_n / (effective_n + model.shrink_prior)
            effects[key] = clamp(mean * shrink)
        if effects:
            output[pollster] = {"bloc_effects": {}, "party_effects": effects}
    return output


def fit_hierarchical_one_level(model: Model) -> dict:
    records: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for poll in model.polls:
        parties = model.party_shares(poll)
        consensus = model.consensus(poll)
        if not parties or not consensus:
            continue
        consensus_parties = consensus[0]
        common = [
            key for key in parties
            if key in consensus_parties
            and parties[key] > 0
            and consensus_parties[key] > 0
        ]
        if len(common) < 2:
            continue
        weight = model.poll_weight(poll)
        log_p = {key: math.log(parties[key]) for key in common}
        log_c = {key: math.log(consensus_parties[key]) for key in common}
        mean_p = sum(log_p.values()) / len(common)
        mean_c = sum(log_c.values()) / len(common)
        for key in common:
            diff = (log_p[key] - mean_p) - (log_c[key] - mean_c)
            entity_weight = weight * math.sqrt(min(parties[key], consensus_parties[key]) + 1e-4)
            records[poll["pollster"]][key].append((diff, entity_weight))

    stats = {}
    global_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for pollster, by_party in records.items():
        stats[pollster] = {}
        for key, values in by_party.items():
            result = weighted_mean(values)
            if not result:
                continue
            mean, effective_n = result
            if effective_n < model.min_effective:
                continue
            stats[pollster][key] = (mean, effective_n)
            global_values[key].append((mean, effective_n))

    global_mean = {}
    for key, values in global_values.items():
        result = weighted_mean(values)
        if result:
            global_mean[key] = result[0]

    output = {}
    for pollster, by_party in stats.items():
        effects = {}
        for key, (mean, effective_n) in by_party.items():
            group = global_mean.get(key, 0.0)
            shrink = effective_n / (effective_n + model.shrink_prior)
            effects[key] = clamp(group + (mean - group) * shrink)
        if effects:
            output[pollster] = {"bloc_effects": {}, "party_effects": effects}
    return output


def apply_one_level(shares: dict[str, float], party_effects: dict[str, float]) -> dict[str, float]:
    adjusted = {
        key: value * math.exp(-party_effects.get(key, 0.0))
        for key, value in shares.items()
    }
    return normalize(adjusted)


def backtest(train_polls: list[dict], test_polls: list[dict], entities_cfg: dict, he_cfg: dict):
    elections = load_yaml("elections.yaml")["elections"]
    train_model = Model(train_polls, entities_cfg, he_cfg, date.fromisoformat("2023-05-14"))
    two_level_effects = train_model.fit()
    one_level_effects = fit_one_level(train_model)

    results = {}
    for election_id, race, label in [
        ("2023-general", "parliamentary", "parliament"),
        ("2023-pres", "presidential_first", "president_first"),
    ]:
        actual = elections[election_id]["races"][race]["actual"]
        eligible = [
            poll for poll in test_polls
            if poll["election_id"] == election_id and poll["race"] == race
        ]
        if not eligible:
            continue
        cutoff = elections[election_id]["date"]
        entity_ids = list(actual)
        baseline = aggregate(eligible, entity_ids, cutoff=cutoff)

        one_level_adjusted = [
            apply_poll_effects(poll, one_level_effects, train_model.bloc_of, one_level=True)
            for poll in eligible
        ]
        one_level = aggregate(one_level_adjusted, entity_ids, cutoff=cutoff)

        two_level_adjusted = [
            apply_poll_effects(poll, two_level_effects, train_model.bloc_of)
            for poll in eligible
        ]
        two_level = aggregate(two_level_adjusted, entity_ids, cutoff=cutoff)

        rows = []
        for key in entity_ids:
            rows.append({
                "entity": key,
                "actual": actual.get(key),
                "baseline": baseline.get(key),
                "one_level": one_level.get(key),
                "two_level": two_level.get(key),
            })

        def mae(field):
            errors = [
                abs(row[field] - row["actual"])
                for row in rows
                if row[field] is not None and row["actual"] is not None
            ]
            return sum(errors) / len(errors) if errors else None

        results[label] = {
            "n_polls": len(eligible),
            "mae_baseline": mae("baseline"),
            "mae_one_level": mae("one_level"),
            "mae_two_level": mae("two_level"),
            "rows": rows,
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true")
    args = parser.parse_args()

    entities_cfg = load_yaml("entities.yaml")
    he_cfg = load_yaml("house_effects.yaml")
    all_polls = load_polls()

    reference_date = max(date.fromisoformat(poll["field_end"]) for poll in all_polls)
    model = Model(all_polls, entities_cfg, he_cfg, reference_date)
    effects = model.fit()
    one_level = fit_one_level(model)
    hierarchical = fit_hierarchical_one_level(model)
    payload = payload_for_web(effects, all_polls, model, one_level, hierarchical)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {WEB_OUT.relative_to(ROOT)} ({len(effects)} pollsters)")

    train = [poll for poll in all_polls if poll["election_id"] in TRAIN_ELECTIONS]
    train_model = Model(train, entities_cfg, he_cfg, date.fromisoformat("2023-05-14"))
    train_effects = train_model.fit()
    train_one_level = fit_one_level(train_model)
    train_hierarchical = fit_hierarchical_one_level(train_model)
    train_payload = payload_for_web(
        train_effects, train, train_model, train_one_level, train_hierarchical
    )
    train_payload["meta"]["training_window"] = "2015-2019"
    train_payload["meta"]["purpose"] = "2023 backtest only"
    WEB_BACKTEST_OUT.write_text(
        json.dumps(train_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {WEB_BACKTEST_OUT.relative_to(ROOT)} ({len(train_effects)} pollsters)")

    if args.backtest:
        results = backtest(train, all_polls, entities_cfg, he_cfg)
        BACKTEST_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {BACKTEST_OUT.relative_to(ROOT)}")
        for label, result in results.items():
            print(
                label, result["n_polls"], "polls",
                "baseline", round(result["mae_baseline"], 4) if result["mae_baseline"] else None,
                "one-level", round(result["mae_one_level"], 4) if result["mae_one_level"] else None,
                "two-level", round(result["mae_two_level"], 4) if result["mae_two_level"] else None,
            )


def apply_poll_effects(poll: dict, effects: dict, bloc_of: dict, one_level: bool = False) -> dict:
    pollster_effect = effects.get(poll["pollster"])
    if not pollster_effect:
        return poll
    shares = normalize({
        key: value for key, value in poll.get("results", {}).items()
        if value is not None and value > 0
    })
    if not shares:
        return poll
    if one_level:
        adjusted = apply_one_level(shares, pollster_effect.get("party_effects", {}))
    else:
        adjusted = apply_effect_set(shares, pollster_effect, bloc_of)
    return {**poll, "results": adjusted}


if __name__ == "__main__":
    main()
