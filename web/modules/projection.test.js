import assert from "node:assert/strict";
import test from "node:test";

import {
  adjustedShare,
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
