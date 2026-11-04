import { addDays, aggregateAt, normalizePoll } from "./aggregate.js";
import {
  MAIN_PARTIES,
  addOther,
  parliamentActual,
} from "./poll_preset.js";

const OTHER = "OTHER";

export const RACES = {
  presidentFirst: {
    key: "presidentFirst",
    label: "Cumhurbaşkanı 1. Tur",
    electionDay: "2023-05-14",
    entities: ["A", "B", "C", "D"],
  },
  presidentRunoff: {
    key: "presidentRunoff",
    label: "Cumhurbaşkanı 2. Tur",
    electionDay: "2023-05-28",
    entities: ["A", "B"],
  },
  parliament: {
    key: "parliament",
    label: "Milletvekili",
    electionDay: "2023-05-14",
    entities: [...MAIN_PARTIES, OTHER],
  },
};

export function entitiesFor(raceKey) {
  return RACES[raceKey]?.entities || [];
}

export function preparePolls(pollPayload, raceKey) {
  if (raceKey === "presidentFirst") {
    return pollPayload.datasets.president.polls.filter((poll) => poll.round === 1);
  }
  if (raceKey === "presidentRunoff") {
    return pollPayload.datasets.president.polls.filter((poll) => poll.round === 2);
  }
  if (raceKey === "parliament") {
    return pollPayload.datasets.parliament.polls.map(addOther);
  }
  return [];
}

export function actualFor(data, raceKey) {
  if (raceKey === "presidentFirst") {
    return data.president.first_round.national.shares;
  }
  if (raceKey === "presidentRunoff") {
    return data.president.runoff.national.shares;
  }
  return parliamentActual(data);
}

export function finalSummary(polls, entities, actual, cutoff, options) {
  const aggregate = aggregateAt(polls, entities, cutoff, options);
  const rows = entities.map((id) => {
    const value = aggregate.shares[id] == null ? null : aggregate.shares[id];
    const target = actual[id] == null ? null : actual[id];
    return {
      id,
      aggregate: value,
      actual: target,
      error: value == null || target == null ? null : value - target,
    };
  });
  const scored = rows.filter((row) => row.error != null);
  const mae = scored.length
    ? scored.reduce((sum, row) => sum + Math.abs(row.error), 0) / scored.length
    : null;
  return {
    aggregate,
    rows,
    mae,
    nPolls: aggregate.nPolls,
    lastPoll: aggregate.lastPoll,
  };
}

export function errorSeries(polls, entities, actual, start, end, options) {
  const points = [];
  let day = start;
  let guard = 0;
  while (day <= end && guard < 1000) {
    const aggregate = aggregateAt(polls, entities, day, options);
    if (aggregate.nPolls > 0) {
      const errors = {};
      let total = 0;
      let count = 0;
      for (const id of entities) {
        const value = aggregate.shares[id];
        const target = actual[id];
        if (value == null || target == null) continue;
        const error = Math.abs(value - target);
        errors[id] = error;
        total += error;
        count += 1;
      }
      if (count) points.push({ date: day, errors, mae: total / count });
    }
    day = addDays(day, 1);
    guard += 1;
  }
  return points;
}

export function pollsterLeaderboard(polls, entities, actual, cutoff) {
  const byPollster = new Map();
  for (const poll of polls) {
    if (poll.field_end > cutoff) continue;
    if (!byPollster.has(poll.pollster)) byPollster.set(poll.pollster, []);
    byPollster.get(poll.pollster).push(poll);
  }

  const rows = [];
  for (const [pollster, list] of byPollster.entries()) {
    const sorted = [...list].sort((a, b) =>
      a.field_end < b.field_end ? -1 : a.field_end > b.field_end ? 1 : 0
    );
    let chosen = null;
    let shares = null;
    for (let index = sorted.length - 1; index >= 0; index -= 1) {
      const candidate = normalizePoll(sorted[index], entities, true);
      if (candidate) {
        chosen = sorted[index];
        shares = candidate;
        break;
      }
    }
    if (!chosen) continue;

    const errors = [];
    let bias = 0;
    let count = 0;
    for (const id of entities) {
      const value = shares[id];
      const target = actual[id];
      if (value == null || target == null) continue;
      errors.push(Math.abs(value - target));
      bias += value - target;
      count += 1;
    }
    if (!errors.length) continue;
    rows.push({
      pollster,
      nPolls: list.length,
      lastPoll: chosen.field_end,
      mae: errors.reduce((sum, value) => sum + value, 0) / errors.length,
      bias: bias / count,
    });
  }
  return rows.sort((a, b) => a.mae - b.mae);
}

export function leaveOneOut(polls, entities, cutoff, options) {
  const base = aggregateAt(polls, entities, cutoff, options);
  const byPollster = new Map();
  for (const poll of polls) {
    if (!byPollster.has(poll.pollster)) byPollster.set(poll.pollster, []);
    byPollster.get(poll.pollster).push(poll);
  }

  const rows = [];
  for (const [pollster, list] of byPollster.entries()) {
    const remaining = polls.filter((poll) => poll.pollster !== pollster);
    if (!remaining.length) continue;
    const aggregate = aggregateAt(remaining, entities, cutoff, options);
    let largest = null;
    for (const id of entities) {
      const delta = (aggregate.shares[id] || 0) - (base.shares[id] || 0);
      if (largest == null || Math.abs(delta) > Math.abs(largest.delta)) {
        largest = { id, delta };
      }
    }
    if (largest) {
      rows.push({
        pollster,
        nPolls: list.length,
        entity: largest.id,
        delta: largest.delta,
        maxAbs: Math.abs(largest.delta),
      });
    }
  }
  return rows.sort((a, b) => b.maxAbs - a.maxAbs);
}
