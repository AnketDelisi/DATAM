import assert from "node:assert/strict";
import test from "node:test";

import {
  applyHierarchical,
  applyHistoricalHouseEffects,
  applyOneLevel,
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
      one_level_effects: {
        bloc_effects: {},
        party_effects: { AKP: 0, MHP: 0, CHP: 0.35, IYI: 0.2 },
      },
      hierarchical_effects: {
        bloc_effects: {},
        party_effects: { AKP: 0, MHP: 0, CHP: 0.25, IYI: 0.15 },
      },
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

test("damping scales the house-effect correction", () => {
  const shares = { AKP: 0.4, MHP: 0.1, CHP: 0.4, IYI: 0.1 };
  const full = applyTwoLevel(shares, payload.pollsters.Biased, payload.meta.bloc_of, 1);
  const half = applyTwoLevel(shares, payload.pollsters.Biased, payload.meta.bloc_of, 0.5);
  assert.ok(half.CHP + half.IYI < 0.5);
  assert.ok(half.CHP + half.IYI > full.CHP + full.IYI);
});

test("one-level correction uses dedicated party effects", () => {
  const shares = { AKP: 0.4, MHP: 0.1, CHP: 0.4, IYI: 0.1 };
  const adjusted = applyOneLevel(shares, payload.pollsters.Biased, 1);
  assert.ok(adjusted.CHP + adjusted.IYI < 0.5);
  assert.ok(adjusted.AKP + adjusted.MHP > 0.5);
});

test("hierarchical correction uses pooled party effects", () => {
  const shares = { AKP: 0.4, MHP: 0.1, CHP: 0.4, IYI: 0.1 };
  const adjusted = applyHierarchical(shares, payload.pollsters.Biased, 1);
  assert.ok(adjusted.CHP + adjusted.IYI < 0.5);
  assert.ok(adjusted.CHP + adjusted.IYI > 0.4);
});

test("meta correction mode selects hierarchical effects", () => {
  const polls = [
    {
      pollster: "Biased",
      results: { P9: 0.4, P11: 0.1, P21: 0.4, P22: 0.1 },
    },
  ];
  const hierarchical = {
    ...payload,
    meta: {
      ...payload.meta,
      correction_strength: { parliamentary: 1 },
      correction_mode: { parliamentary: "hierarchical" },
    },
  };
  const [adjusted] = applyHistoricalHouseEffects(polls, "parliament", hierarchical);
  assert.ok(adjusted.results.P21 + adjusted.results.P22 < 0.5);
});

test("meta correction mode selects one-level effects", () => {
  const polls = [
    {
      pollster: "Biased",
      results: { P9: 0.4, P11: 0.1, P21: 0.4, P22: 0.1 },
    },
  ];
  const oneLevel = {
    ...payload,
    meta: {
      ...payload.meta,
      correction_strength: { parliamentary: 1 },
      correction_mode: { parliamentary: "one_level" },
    },
  };
  const [adjusted] = applyHistoricalHouseEffects(polls, "parliament", oneLevel);
  assert.ok(adjusted.results.P21 + adjusted.results.P22 < 0.5);
});

test("meta correction strength can disable historical effects", () => {
  const polls = [{ pollster: "Biased", results: { P9: 0.4, P11: 0.1, P21: 0.4, P22: 0.1 } }];
  const disabled = {
    ...payload,
    meta: { ...payload.meta, correction_strength: { parliamentary: 0 } },
  };
  const [adjusted] = applyHistoricalHouseEffects(polls, "parliament", disabled);
  assert.equal(adjusted, polls[0]);
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

test("largest effect follows the configured one-level mode", () => {
  const oneLevel = {
    ...payload,
    meta: {
      ...payload.meta,
      correction_mode: { parliamentary: "one_level" },
    },
  };
  const largest = largestHistoricalEffect(oneLevel, "parliament", "Biased");
  assert.equal(largest.id, "P21");
  assert.equal(largest.value, 0.35);
});
