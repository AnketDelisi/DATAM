export const PARTY_OUTCOME = {
  P9: "AKP",
  P21: "CHP",
  P11: "MHP",
  P22: "IYI",
  P12: "HDP_DEM",
  P10: "YRP",
  P13: "TIP",
  P24: "ZP",
};

export const CANDIDATE_OUTCOME = {
  A: "erdogan",
  B: "kilicdaroglu",
  C: "ogan",
  D: "ince",
};

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
