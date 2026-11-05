import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { normalizeName } from "./format.js";
import {
  correlationsFor,
  domain,
  formatMetric,
  linearRegression,
} from "./demographics.js";

test("formatMetric treats medyan yaş separately", () => {
  assert.equal(formatMetric("median_age", 33.45), "33.5");
  assert.equal(formatMetric("female_share", 0.5012), "50.1%");
});

test("linearRegression recovers a straight line", () => {
  const line = linearRegression([
    { x: 0, y: 1 },
    { x: 1, y: 3 },
    { x: 2, y: 5 },
  ]);
  assert.ok(Math.abs(line.slope - 2) < 1e-9);
  assert.ok(Math.abs(line.intercept - 1) < 1e-9);
});

test("correlationsFor sorts by absolute Pearson r", () => {
  const rows = correlationsFor(
    [
      { outcome: "CHP", demographic: "a", pearson_r: 0.1 },
      { outcome: "CHP", demographic: "b", pearson_r: -0.7 },
      { outcome: "AKP", demographic: "c", pearson_r: 0.9 },
    ],
    "CHP"
  );
  assert.deepEqual(rows.map((row) => row.demographic), ["b", "a"]);
});

test("province shapes join to the demographics payload", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/demographics.json", import.meta.url), "utf8")
  );
  const geo = JSON.parse(
    readFileSync(new URL("../geo/tr-provinces.geojson", import.meta.url), "utf8")
  );
  const keys = new Set(data.provinces.map((row) => row.key));
  assert.equal(geo.features.length, 81);
  assert.equal(keys.size, 81);
  for (const feature of geo.features) {
    assert.ok(keys.has(normalizeName(feature.properties.shapeName)));
  }
});

test("domain pads a constant series", () => {
  const [low, high] = domain([0.5, 0.5]);
  assert.ok(low < 0.5 && high > 0.5);
});
