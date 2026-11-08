export const RACE_ENTITY_MAP = {
  presidentFirst: {
    A: "ERDOGAN",
    B: "KILICDAROGLU",
    C: "OGAN",
    D: "INCE",
  },
  presidentRunoff: {
    A: "ERDOGAN",
    B: "KILICDAROGLU",
  },
  parliament: {
    P9: "AKP",
    P21: "CHP",
    P11: "MHP",
    P22: "IYI",
    P12: "HDP_DEM",
    P10: "YRP",
    P13: "TIP",
    P24: "ZP",
    OTHER: "OTHER",
  },
};

export function pollsterKey(value) {
  return String(value)
    .toLocaleUpperCase("tr-TR")
    .replace(/\u0130/g, "I")
    .replace(/\u015e/g, "S")
    .replace(/\u011e/g, "G")
    .replace(/\u00c7/g, "C")
    .replace(/\u00d6/g, "O")
    .replace(/\u00dc/g, "U")
    .replace(/\u00c2/g, "A")
    .replace(/[^A-Z0-9]/g, "");
}

const RACE_STRENGTH_KEY = {
  parliament: "parliamentary",
  presidentFirst: "presidential_first",
  presidentRunoff: "presidential_runoff",
};

function normalize(values) {
  const clean = {};
  let total = 0;
  for (const [key, value] of Object.entries(values)) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      clean[key] = value;
      total += value;
    }
  }
  if (total <= 0) return null;
  for (const key of Object.keys(clean)) clean[key] /= total;
  return clean;
}

export function applyTwoLevel(shares, pollsterEffect, blocOf = {}, strength = 1) {
  const blocEffects = pollsterEffect?.bloc_effects || {};
  const partyEffects = pollsterEffect?.party_effects || {};
  const weight = Math.max(0, Math.min(1, Number(strength) || 0));
  let adjusted = {};
  for (const [key, value] of Object.entries(shares)) {
    const bloc = blocOf[key] || "OTHER";
    adjusted[key] = value * Math.exp(-(blocEffects[bloc] || 0) * weight);
  }
  adjusted = normalize(adjusted);
  if (!adjusted) return null;

  const groups = {};
  for (const key of Object.keys(adjusted)) {
    const bloc = blocOf[key] || "OTHER";
    (groups[bloc] ||= []).push(key);
  }
  for (const keys of Object.values(groups)) {
    const before = keys.reduce((sum, key) => sum + adjusted[key], 0);
    if (before <= 0) continue;
    for (const key of keys) {
      adjusted[key] *= Math.exp(-(partyEffects[key] || 0) * weight);
    }
    const after = keys.reduce((sum, key) => sum + adjusted[key], 0);
    if (after > 0) {
      for (const key of keys) adjusted[key] *= before / after;
    }
  }
  return normalize(adjusted);
}

function applyPartyEffects(shares, partyEffects, strength) {
  const weight = Math.max(0, Math.min(1, Number(strength) || 0));
  const adjusted = {};
  for (const [key, value] of Object.entries(shares)) {
    adjusted[key] = value * Math.exp(-(partyEffects[key] || 0) * weight);
  }
  return normalize(adjusted);
}

export function applyOneLevel(shares, pollsterEffect, strength = 1) {
  const partyEffects =
    pollsterEffect?.one_level_effects?.party_effects ||
    pollsterEffect?.party_effects ||
    {};
  return applyPartyEffects(shares, partyEffects, strength);
}

export function applyHierarchical(shares, pollsterEffect, strength = 1) {
  const partyEffects =
    pollsterEffect?.hierarchical_effects?.party_effects ||
    pollsterEffect?.one_level_effects?.party_effects ||
    pollsterEffect?.party_effects ||
    {};
  return applyPartyEffects(shares, partyEffects, strength);
}

export function applyHistoricalHouseEffects(polls, raceKey, payload, strength) {
  const entityMap = RACE_ENTITY_MAP[raceKey];
  if (!entityMap || !payload?.pollsters) return polls;
  const configured = payload.meta?.correction_strength?.[RACE_STRENGTH_KEY[raceKey]];
  const weight = Number.isFinite(strength)
    ? strength
    : Number.isFinite(configured)
      ? configured
      : 1;
  if (weight <= 0) return polls;
  const raceStrengthKey = RACE_STRENGTH_KEY[raceKey];
  const mode = payload.meta?.correction_mode?.[raceStrengthKey] || "two_level";
  const blocOf = payload.meta?.bloc_of || {};
  const byKey = new Map(
    Object.entries(payload.pollsters).map(([name, effect]) => [pollsterKey(name), effect])
  );
  const reverse = {};
  for (const [uiId, canonical] of Object.entries(entityMap)) {
    if (!(canonical in reverse)) reverse[canonical] = uiId;
  }

  return polls.map((poll) => {
    const effect = payload.pollsters[poll.pollster] || byKey.get(pollsterKey(poll.pollster));
    if (!effect) return poll;
    const canonical = {};
    for (const [uiId, value] of Object.entries(poll.results || {})) {
      const key = entityMap[uiId];
      if (!key) continue;
      if (typeof value === "number" && Number.isFinite(value) && value > 0) {
        canonical[key] = (canonical[key] || 0) + value;
      }
    }
    const shares = normalize(canonical);
    if (!shares) return poll;
    const adjusted =
      mode === "hierarchical"
        ? applyHierarchical(shares, effect, weight)
        : mode === "one_level"
          ? applyOneLevel(shares, effect, weight)
          : applyTwoLevel(shares, effect, blocOf, weight);
    if (!adjusted) return poll;
    const results = {};
    for (const [key, value] of Object.entries(adjusted)) {
      const uiId = reverse[key];
      if (uiId) results[uiId] = value;
    }
    return Object.keys(results).length ? { ...poll, results } : poll;
  });
}

export function largestHistoricalEffect(payload, raceKey, pollster) {
  const effect = payload?.pollsters?.[pollster];
  const entityMap = RACE_ENTITY_MAP[raceKey];
  if (!effect || !entityMap) return null;
  const reverse = {};
  for (const [uiId, canonical] of Object.entries(entityMap)) {
    if (!(canonical in reverse)) reverse[canonical] = uiId;
  }
  const mode = payload.meta?.correction_mode?.[RACE_STRENGTH_KEY[raceKey]] || "two_level";
  const values =
    mode === "hierarchical"
      ? effect.hierarchical_effects?.party_effects ||
        effect.one_level_effects?.party_effects ||
        {}
      : mode === "one_level"
        ? effect.one_level_effects?.party_effects || {}
        : effect.total_effects || {};
  let largest = null;
  for (const [canonical, value] of Object.entries(values)) {
    const uiId = reverse[canonical];
    if (!uiId || !Number.isFinite(value)) continue;
    if (!largest || Math.abs(value) > Math.abs(largest.value)) {
      largest = { id: uiId, value };
    }
  }
  return largest;
}
