export const PARTY_OUTCOME = {
  P9: "AKP_swing",
  P21: "CHP_swing",
  P11: "MHP_swing",
  P22: "IYI_swing",
  P12: "HDP_DEM_swing",
  P10: null,
  P13: null,
  P24: null,
};

export const CANDIDATE_OUTCOME = {
  A: "erdogan",
  B: "kilicdaroglu",
  C: "ogan",
  D: "ince",
};

export const PARTY_STRENGTH = {
  P9: 0.6,
  P21: 0.4,
  P11: 0.2,
  P22: 0.2,
  P12: 0.7,
};

export function scaledStrength(id, strength) {
  const base = PARTY_STRENGTH[id];
  if (!base || !Number.isFinite(strength)) return 0;
  return Math.max(0, Math.min(1, (strength * base) / 0.6));
}

export function tiltFor(swingData, provinceKey, outcome) {
  if (!swingData?.provinces || !outcome) return 0;
  return swingData.provinces[provinceKey]?.[outcome] || 0;
}

export function swingFactor(nationalFactor, tilt, strength) {
  if (!Number.isFinite(nationalFactor)) return 1;
  const sensitivity = 1 + Math.max(0, Math.min(1, strength)) * tilt;
  return Math.max(0, 1 + (nationalFactor - 1) * sensitivity);
}

export function adjustedShare(base, delta, tilt, strength) {
  const sensitivity = 1 + Math.max(0, Math.min(1, strength)) * tilt;
  return Math.max(0, base + delta * sensitivity);
}

export function rakeToTargets(districts, targets, iterations = 10) {
  const rows = districts.map((district) => ({
    ...district,
    votes: { ...district.votes },
  }));
  const districtTotals = rows.map((district) => {
    const total = district.valid_votes;
    if (Number.isFinite(total) && total > 0) return total;
    return Object.values(district.votes).reduce((sum, value) => sum + (value || 0), 0);
  });
  const partyIds = Object.keys(targets).filter((id) =>
    Number.isFinite(targets[id]) && targets[id] >= 0
  );

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    for (const id of partyIds) {
      let current = 0;
      for (const row of rows) current += row.votes[id] || 0;
      if (current <= 0) continue;
      const scale = targets[id] / current;
      for (const row of rows) {
        if (row.votes[id] != null) row.votes[id] *= scale;
      }
    }

    rows.forEach((row, index) => {
      const total = Object.values(row.votes).reduce(
        (sum, value) => sum + (value || 0),
        0
      );
      if (total <= 0 || districtTotals[index] <= 0) return;
      const scale = districtTotals[index] / total;
      for (const id of Object.keys(row.votes)) row.votes[id] *= scale;
    });
  }
  return rows;
}
