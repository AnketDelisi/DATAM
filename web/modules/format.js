const pct = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const whole = new Intl.NumberFormat("tr-TR", {
  maximumFractionDigits: 0,
});

export function normalizeName(value) {
  return String(value)
    .toLocaleUpperCase("tr-TR")
    .replace(/İ/g, "I")
    .replace(/Ş/g, "S")
    .replace(/Ğ/g, "G")
    .replace(/Ç/g, "C")
    .replace(/Ö/g, "O")
    .replace(/Ü/g, "U")
    .replace(/Â/g, "A")
    .trim();
}

export function formatPct(value, digits = 1) {
  if (!Number.isFinite(value)) return "–";
  return `${pct.format(value)}%`;
}

export function formatInt(value) {
  if (!Number.isFinite(value)) return "–";
  return whole.format(value);
}

export function formatSigned(value) {
  if (!Number.isFinite(value) || value === 0) return "0";
  return `${value > 0 ? "+" : ""}${formatInt(value)}`;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
