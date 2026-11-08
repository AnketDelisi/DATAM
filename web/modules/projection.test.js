import assert from "node:assert/strict";
import test from "node:test";

import {
  adjustedShare,
  rakeToTargets,
  scaledStrength,
  swingFactor,
  tiltFor,
} from "./projection.js";

const swing = {
  provinces: {
    ADANA: { AKP: 1, CHP: -1 },
  },
};

test("tilt lookup is province and outcome specific", () => {
  assert.equal(tiltFor(swing, "ADANA", "AKP"), 1);
  assert.equal(tiltFor(swing, "ADANA", "CHP"), -1);
  assert.equal(tiltFor(swing, "ANKARA", "AKP"), 0);
});

test("zero strength reproduces the uniform swing", () => {
  assert.equal(swingFactor(1.2, 1, 0), 1.2);
  assert.equal(adjustedShare(0.4, 0.1, -1, 0), 0.5);
});

test("positive tilt amplifies a positive national factor", () => {
  assert.ok(swingFactor(1.2, 1, 0.5) > 1.2);
  assert.ok(swingFactor(1.2, -1, 0.5) < 1.2);
});

test("party strengths use their own best backtest values at 60%", () => {
  assert.equal(scaledStrength("P9", 0.6), 0.6);
  assert.ok(Math.abs(scaledStrength("P21", 0.6) - 0.4) < 1e-12);
  assert.ok(Math.abs(scaledStrength("P22", 0.6) - 0.2) < 1e-12);
  assert.equal(scaledStrength("P10", 0.6), 0);
  assert.equal(scaledStrength("P12", 1), 1);
});

test("raking preserves national party targets and district totals", () => {
  const districts = [
    { valid_votes: 100, votes: { A: 70, B: 30 } },
    { valid_votes: 100, votes: { A: 50, B: 50 } },
  ];
  const result = rakeToTargets(districts, { A: 100, B: 100 }, 20);
  const a = result.reduce((sum, row) => sum + row.votes.A, 0);
  const b = result.reduce((sum, row) => sum + row.votes.B, 0);
  assert.ok(Math.abs(a - 100) < 1e-6);
  assert.ok(Math.abs(b - 100) < 1e-6);
  for (const row of result) {
    assert.ok(Math.abs(row.votes.A + row.votes.B - 100) < 1e-6);
  }

  const zero = rakeToTargets(districts, { A: 200, B: 0 }, 20);
  assert.ok(Math.abs(zero.reduce((sum, row) => sum + row.votes.A, 0) - 200) < 1e-6);
  assert.ok(zero.every((row) => Math.abs(row.votes.B) < 1e-9));
});
