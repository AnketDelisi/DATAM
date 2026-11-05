import assert from "node:assert/strict";
import test from "node:test";

import {
  applyHistoricalHouseEffects,
  applyTwoLevel,
  largestHistoricalEffect,
  pollsterKey,
} from "./historical_effects.js";

const payload = {
  meta: {
    bloc_of: {
      AKP: "INCUMBENT",
      MHP: "INCUMBENT",
      CHP: "OPPOSITION",
      IYI: "OPPOSITION",
    },
  },
  pollsters: {
    Biased: {
      bloc_effects: { INCUMBENT: 0, OPPOSITION: 0.2 },
      party_effects: { AKP: 0, MHP: 0, CHP: 0, IYI: 0 },
      total_effects: { AKP: 0, MHP: 0, CHP: 0.2, IYI: 0.2 },
    },
  },
};

test("bloc correction lowers over-reported opposition", () => {
  const shares = { AKP: 0.4, MHP: 0.1, CHP: 0.4, IYI: 0.1 };
  const adjusted = applyTwoLevel(shares, payload.pollsters.Biased, payload.meta.bloc_of);
  assert.ok(adjusted.CHP + adjusted.IYI < 0.5);
  assert.ok(Math.abs(Object.values(adjusted).reduce((a, b) => a + b, 0) - 1) < 1e-9);
});

test("historical effects map UI ids back to poll ids", () => {
  const polls = [
    {
      pollster: "Biased",
      field_end: "2023-05-01",
      results: { P9: 0.4, P11: 0.1, P21: 0.4, P22: 0.1 },
    },
  ];
  const [adjusted] = applyHistoricalHouseEffects(polls, "parliament", payload);
  assert.ok(adjusted.results.P21 + adjusted.results.P22 < 0.5);
  assert.ok(adjusted.results.P9 > 0.4);
});

test("unknown pollsters pass through untouched", () => {
  const polls = [{ pollster: "Unknown", results: { P9: 1 } }];
  const [adjusted] = applyHistoricalHouseEffects(polls, "parliament", payload);
  assert.equal(adjusted, polls[0]);
});

test("pollster keys ignore case and punctuation", () => {
  assert.equal(pollsterKey("Area"), pollsterKey("AREA"));
  assert.equal(pollsterKey("BET\u0130MAR"), pollsterKey("BETIMAR"));
});

test("largest effect uses the race entity map", () => {
  const largest = largestHistoricalEffect(payload, "parliament", "Biased");
  assert.equal(largest.id, "P21");
});
