import {
  applyHouseEffects,
  estimateHouseEffects,
  medianSample,
  normalizePoll,
  weightedAverage,
} from "./aggregate.js";

function mulberry32(seed) {
  let value = seed >>> 0;
  return function random() {
    value += 0x6d2b79f5;
    let result = value;
    result = Math.imul(result ^ (result >>> 15), result | 1);
    result ^= result + Math.imul(result ^ (result >>> 7), result | 61);
    return ((result ^ (result >>> 14)) >>> 0) / 4294967296;
  };
}

function randomNormal(random) {
  let u = 0;
  let v = 0;
  while (u === 0) u = random();
  while (v === 0) v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function exponentialWeight(random) {
  return -Math.log(Math.max(random(), 1e-12));
}

function percentile(values, probability) {
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sorted[lower];
  const weight = position - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

export function bootstrapAggregate(
  polls,
  entities,
  cutoff,
  options = {},
  draws = 500,
  seed = 20230514
) {
  const filtered = polls.filter((poll) => poll.field_end <= cutoff);
  const defaultSample = options.defaultSample || medianSample(filtered);
  const normalize = options.normalize !== false;
  const houseEffects = options.houseEffects && normalize;

  let effects = null;
  let basePolls = filtered;
  if (houseEffects) {
    effects = estimateHouseEffects(filtered, entities, cutoff, {
      halfLifeDays: options.halfLifeDays ?? 28,
      defaultSample,
    });
    basePolls = applyHouseEffects(filtered, entities, effects, normalize);
  }

  const point = weightedAverage(basePolls, entities, cutoff, {
    ...options,
    defaultSample,
  });
  const random = mulberry32(seed);
  const samples = Object.fromEntries(entities.map((id) => [id, []]));

  for (let draw = 0; draw < draws; draw += 1) {
    const simulated = [];
    for (const poll of basePolls) {
      const shares = normalizePoll(poll, entities, normalize);
      if (!shares) continue;
      const sampleSize = Math.max(poll.sample_size || defaultSample, 50);
      const noisy = {};
      let total = 0;
      for (const [id, value] of Object.entries(shares)) {
        const standardError = Math.sqrt(
          Math.max(value * (1 - value), 1e-4) / sampleSize
        );
        const sampled = Math.max(
          0,
          value + randomNormal(random) * standardError
        );
        noisy[id] = sampled;
        total += sampled;
      }
      if (total <= 0) continue;
      if (normalize) {
        for (const id of Object.keys(noisy)) noisy[id] /= total;
      }
      simulated.push({ ...poll, results: noisy });
    }
    if (!simulated.length) continue;

    const result = weightedAverage(simulated, entities, cutoff, {
      ...options,
      defaultSample,
      weightFn: () => exponentialWeight(random),
    });
    for (const id of entities) {
      if (result.shares[id] != null) samples[id].push(result.shares[id]);
    }
  }

  const intervals = {};
  for (const id of entities) {
    const values = samples[id];
    intervals[id] = values.length
      ? {
          low: percentile(values, 0.05),
          median: percentile(values, 0.5),
          high: percentile(values, 0.95),
        }
      : null;
  }

  return {
    point: point.shares,
    intervals,
    draws,
    nPolls: point.nPolls,
    effects,
  };
}
