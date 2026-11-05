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
    weightFn = null,
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
    const weight = recency * Math.sqrt(sample) * (weightFn ? weightFn(poll) : 1);
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

export function aggregateAt(
  polls,
  entities,
  cutoff,
  { halfLifeDays = 28, normalize = true, defaultSample = 1000 } = {}
) {
  const filtered = polls.filter((poll) => poll.field_end <= cutoff);
  const result = weightedAverage(filtered, entities, cutoff, {
    halfLifeDays,
    normalize,
    defaultSample,
  });
  return { ...result, polls: filtered };
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
