import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  aggregateAt,
  medianSample,
  normalizePoll,
} from "./aggregate.js";

test("normalizePoll ignores missing values", () => {
  const poll = {
    pollster: "A",
    field_end: "2023-05-01",
    sample_size: 1000,
    results: { A: 40, B: 60, C: null },
  };
  const shares = normalizePoll(poll, ["A", "B", "C"], true);
  assert.ok(Math.abs(shares.A - 0.4) < 1e-9);
  assert.ok(Math.abs(shares.B - 0.6) < 1e-9);
  assert.equal(shares.C, undefined);
});

test("recency weighting favors the newer poll", () => {
  const polls = [
    {
      pollster: "Old",
      field_end: "2023-05-01",
      sample_size: 1000,
      results: { A: 0.4, B: 0.6 },
    },
    {
      pollster: "New",
      field_end: "2023-05-10",
      sample_size: 1000,
      results: { A: 0.6, B: 0.4 },
    },
  ];
  const result = aggregateAt(polls, ["A", "B"], "2023-05-10", {
    halfLifeDays: 7,
  });
  assert.ok(result.shares.A > 0.5);
  assert.ok(result.shares.B < 0.5);
});

test("2023 presidential first-round aggregate is in the expected range", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
  );
  const polls = data.datasets.president.polls.filter((poll) => poll.round === 1);
  const result = aggregateAt(polls, ["A", "B", "C", "D"], "2023-05-14", {
    halfLifeDays: 28,
    defaultSample: medianSample(polls),
  });
  assert.equal(result.nPolls, 82);
  assert.ok(result.shares.A > 0.44 && result.shares.A < 0.49);
  assert.ok(result.shares.B > 0.44 && result.shares.B < 0.49);
  const total = Object.values(result.shares).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(total - 1) < 1e-9);
});

test("2023 runoff aggregate is in the expected range", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
  );
  const polls = data.datasets.president.polls.filter((poll) => poll.round === 2);
  const result = aggregateAt(polls, ["A", "B"], "2023-05-28", {
    halfLifeDays: 28,
    defaultSample: medianSample(polls),
  });
  assert.equal(result.nPolls, 14);
  assert.ok(result.shares.A > 0.5 && result.shares.A < 0.55);
});

test("2023 parliamentary aggregate uses the main parties", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
  );
  const main = ["P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24"];
  const polls = data.datasets.parliament.polls.map((poll) => {
    const other = Object.entries(poll.results)
      .filter(([id, value]) => !main.includes(id) && typeof value === "number")
      .reduce((sum, [, value]) => sum + value, 0);
    return { ...poll, results: { ...poll.results, OTHER: other } };
  });
  const entities = [...main, "OTHER"];
  const result = aggregateAt(polls, entities, "2023-05-14", {
    halfLifeDays: 28,
    defaultSample: medianSample(polls),
  });
  assert.equal(result.nPolls, 49);
  assert.ok(result.shares.P9 > 0.35 && result.shares.P9 < 0.39);
  assert.ok(result.shares.P21 > 0.26 && result.shares.P21 < 0.30);
});
