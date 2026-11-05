export const OUTCOME_LABELS = {
  erdogan: "Erdoğan",
  kilicdaroglu: "Kılıçdaroğlu",
  ogan: "Oğan",
  ince: "İnce",
  turnout: "Katılım",
  incumbent_swing: "2018 → 2023 iktidar değişimi",
  AKP: "AKP",
  CHP: "CHP",
  MHP: "MHP",
  IYI: "İYİ Parti",
  HDP_DEM: "HDP/DEM",
  YRP: "Yeniden Refah",
  TIP: "TİP",
  ZP: "Zafer Partisi",
};

export const DEMOGRAPHIC_LABELS = {
  female_share: "Kadın oranı",
  median_age: "Medyan yaş",
  hh_1_2: "1–2 kişilik hane",
  hh_3_4: "3–4 kişilik hane",
  hh_5plus: "5+ kişilik hane",
  edu_primary: "İlkokul ve altı",
  edu_secondary: "Ortaokul",
  edu_high_school: "Lise",
  edu_university: "Üniversite",
};

export const REGION_COLORS = {
  Marmara: "#1b1b1b",
  Ege: "#3d5a80",
  Akdeniz: "#b23a2b",
  "Ic Anadolu": "#6b5b3e",
  Karadeniz: "#2f6b4f",
  "Dogu Anadolu": "#6d597a",
  "Guneydogu Anadolu": "#a36b1e",
};

export const REGION_LABELS = {
  Marmara: "Marmara",
  Ege: "Ege",
  Akdeniz: "Akdeniz",
  "Ic Anadolu": "?? Anadolu",
  Karadeniz: "Karadeniz",
  "Dogu Anadolu": "Do?u Anadolu",
  "Guneydogu Anadolu": "G?neydo?u Anadolu",
};

export function formatRegion(key) {
  return REGION_LABELS[key] || key;
}

export function formatOutcome(key) {
  return OUTCOME_LABELS[key] || key;
}

export function formatDemographic(key) {
  return DEMOGRAPHIC_LABELS[key] || key;
}

export function isShare(key) {
  return key !== "median_age";
}

export function formatMetric(key, value, digits = 1) {
  if (!Number.isFinite(value)) return "–";
  if (!isShare(key)) return value.toFixed(digits);
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatCorrelation(value) {
  if (!Number.isFinite(value)) return "–";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function regionColor(region) {
  return REGION_COLORS[region] || "#777";
}

export function correlationsFor(correlations, outcome) {
  return correlations
    .filter((row) => row.outcome === outcome)
    .sort((a, b) => Math.abs(b.pearson_r) - Math.abs(a.pearson_r));
}

export function linearRegression(points) {
  if (points.length < 2) return null;
  let sumX = 0;
  let sumY = 0;
  let sumXX = 0;
  let sumXY = 0;
  for (const point of points) {
    sumX += point.x;
    sumY += point.y;
    sumXX += point.x * point.x;
    sumXY += point.x * point.y;
  }
  const n = points.length;
  const denominator = n * sumXX - sumX * sumX;
  if (Math.abs(denominator) < 1e-12) return null;
  const slope = (n * sumXY - sumX * sumY) / denominator;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

export function domain(values, padding = 0.08) {
  const finite = values.filter((value) => Number.isFinite(value));
  if (!finite.length) return [0, 1];
  let min = Math.min(...finite);
  let max = Math.max(...finite);
  if (min === max) {
    min -= 0.01;
    max += 0.01;
  }
  const span = max - min;
  return [min - span * padding, max + span * padding];
}
