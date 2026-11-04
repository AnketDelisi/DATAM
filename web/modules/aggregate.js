const DAY = 86400000;

export function toDate(value) {
  return new Date(`${value}T00:00:00Z`);
}

export function toDateString(value) {
  return value.toISOString().slice(0, 10);
}

export function dayDiff(from, to) {
  return Math.floor((toDate(to) - toDate(from)) / DAY);
}

export function addDays(value, days) {
  const date = toDate(value);
  date.setUTCDate(date.getUTCDate() + days);
  return toDateString(date);
}

export function normalizePoll(poll, entities, normalize = true) {
  const values = {};
  let total = 0;
  for (const id of entities) {
    const value = poll.results?.[id];
    if (typeof value === "number" && Number.isFinite(value)) {
      values[id] = value;
      total += value;
    }
  }
  if (total <= 0) return null;
  if (normalize) {
    for (const id of Object.keys(values)) values[id] /= total;
  }
  return values;
}

export function weightedAverage(
  polls,
  entities,
  cutoff,
  {
    halfLifeDays = 28,
    normalize = true,
    defaultSample = 1000,
  } = {}
) {
  const sums = {};
  const weights = {};
  let nPolls = 0;
  let lastPoll = null;

  for (const poll of polls) {
    if (poll.field_end > cutoff) continue;
    const shares = normalizePoll(poll, entities, normalize);
    if (!shares) continue;
    const age = Math.max(0, dayDiff(poll.field_end, cutoff));
    const recency = Math.pow(0.5, age / halfLifeDays);
    const sample = poll.sample_size || defaultSample;
    const weight = recency * Math.sqrt(sample);
    for (const [id, value] of Object.entries(shares)) {
      sums[id] = (sums[id] || 0) + value * weight;
      weights[id] = (weights[id] || 0) + weight;
    }
    nPolls += 1;
    if (!lastPoll || poll.field_end > lastPoll) lastPoll = poll.field_end;
  }

  const shares = {};
  for (const id of entities) {
    if (weights[id]) shares[id] = sums[id] / weights[id];
  }
  if (normalize) {
    const total = Object.values(shares).reduce((sum, value) => sum + value, 0);
    if (total > 0) {
      for (const id of Object.keys(shares)) shares[id] /= total;
    }
  }
  return { shares, nPolls, lastPoll };
}

export function estimateHouseEffects(
  polls,
  entities,
  cutoff,
  { halfLifeDays = 28, defaultSample = 1000 } = {}
) {
  const filtered = polls.filter((poll) => poll.field_end <= cutoff);
  const byPollster = new Map();

  for (const poll of filtered) {
    const others = filtered.filter(
      (candidate) => candidate.pollster !== poll.pollster
    );
    const preliminary = weightedAverage(others, entities, poll.field_end, {
      halfLifeDays,
      normalize: true,
      defaultSample,
    });
    if (preliminary.nPolls === 0) continue;
    const shares = normalizePoll(poll, entities, true);
    if (!shares) continue;
    let entry = byPollster.get(poll.pollster);
    if (!entry) {
      entry = { n: 0, sums: {}, counts: {} };
      byPollster.set(poll.pollster, entry);
    }
    entry.n += 1;
    for (const [id, value] of Object.entries(shares)) {
      if (preliminary.shares[id] === undefined) continue;
      entry.sums[id] = (entry.sums[id] || 0) + (value - preliminary.shares[id]);
      entry.counts[id] = (entry.counts[id] || 0) + 1;
    }
  }

  const effects = {};
  for (const [pollster, entry] of byPollster.entries()) {
    const values = {};
    for (const [id, sum] of Object.entries(entry.sums)) {
      const count = entry.counts[id];
      const mean = sum / count;
      values[id] = mean * (count / (count + 2));
    }
    effects[pollster] = { n: entry.n, effects: values };
  }
  return effects;
}

export function applyHouseEffects(polls, entities, effects, normalize = true) {
  return polls.map((poll) => {
    const shares = normalizePoll(poll, entities, true);
    if (!shares) return poll;
    const adjustment = effects[poll.pollster]?.effects || {};
    const adjusted = {};
    let total = 0;
    for (const [id, value] of Object.entries(shares)) {
      const corrected = Math.max(0, value - (adjustment[id] || 0));
      adjusted[id] = corrected;
      total += corrected;
    }
    if (total <= 0) return poll;
    const results = {};
    for (const [id, value] of Object.entries(adjusted)) {
      results[id] = normalize ? value / total : value;
    }
    return { ...poll, results };
  });
}

export function aggregateAt(
  polls,
  entities,
  cutoff,
  {
    halfLifeDays = 28,
    normalize = true,
    houseEffects = false,
    defaultSample = 1000,
  } = {}
) {
  const filtered = polls.filter((poll) => poll.field_end <= cutoff);
  let adjusted = filtered;
  let effects = null;

  if (houseEffects && normalize) {
    effects = estimateHouseEffects(filtered, entities, cutoff, {
      halfLifeDays,
      defaultSample,
    });
    adjusted = applyHouseEffects(filtered, entities, effects, normalize);
  }

  const result = weightedAverage(adjusted, entities, cutoff, {
    halfLifeDays,
    normalize,
    defaultSample,
  });
  return { ...result, effects, polls: filtered };
}

export function buildTrend(
  polls,
  entities,
  start,
  end,
  options = {}
) {
  const points = [];
  if (!start || !end || start > end) return points;
  let day = start;
  let guard = 0;
  while (day <= end && guard < 1000) {
    const aggregate = aggregateAt(polls, entities, day, options);
    if (aggregate.nPolls > 0) {
      points.push({ date: day, shares: aggregate.shares });
    }
    day = addDays(day, 1);
    guard += 1;
  }
  return points;
}

export function medianSample(polls) {
  const samples = polls
    .map((poll) => poll.sample_size)
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => a - b);
  if (!samples.length) return 1000;
  return samples[Math.floor(samples.length / 2)];
}
