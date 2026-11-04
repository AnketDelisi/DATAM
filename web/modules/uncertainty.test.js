import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { medianSample } from "./aggregate.js";
import { bootstrapAggregate } from "./uncertainty.js";

const pollPayload = JSON.parse(
  readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
);

test("small samples produce wider intervals", () => {
  const small = bootstrapAggregate(
    [
      {
        pollster: "Small",
        field_end: "2023-05-01",
        sample_size: 100,
        results: { A: 0.5, B: 0.5 },
      },
    ],
    ["A", "B"],
    "2023-05-01",
    { halfLifeDays: 28, normalize: true },
    300
  );
  const large = bootstrapAggregate(
    [
      {
        pollster: "Large",
        field_end: "2023-05-01",
        sample_size: 10000,
        results: { A: 0.5, B: 0.5 },
      },
    ],
    ["A", "B"],
    "2023-05-01",
    { halfLifeDays: 28, normalize: true },
    300
  );
  const smallWidth = small.intervals.A.high - small.intervals.A.low;
  const largeWidth = large.intervals.A.high - large.intervals.A.low;
  assert.ok(smallWidth > largeWidth);
});

test("bootstrap is deterministic for a fixed seed", () => {
  const polls = [
    {
      pollster: "A",
      field_end: "2023-05-01",
      sample_size: 1000,
      results: { A: 0.5, B: 0.5 },
    },
    {
      pollster: "B",
      field_end: "2023-05-02",
      sample_size: 1000,
      results: { A: 0.52, B: 0.48 },
    },
  ];
  const first = bootstrapAggregate(
    polls,
    ["A", "B"],
    "2023-05-02",
    { halfLifeDays: 28, normalize: true },
    200,
    42
  );
  const second = bootstrapAggregate(
    polls,
    ["A", "B"],
    "2023-05-02",
    { halfLifeDays: 28, normalize: true },
    200,
    42
  );
  assert.deepEqual(first.intervals, second.intervals);
});

test("2023 first-round aggregate intervals cover the point estimate", () => {
  const polls = pollPayload.datasets.president.polls.filter(
    (poll) => poll.round === 1
  );
  const result = bootstrapAggregate(
    polls,
    ["A", "B", "C", "D"],
    "2023-05-14",
    {
      halfLifeDays: 28,
      normalize: true,
      houseEffects: false,
      defaultSample: medianSample(polls),
    },
    300
  );
  assert.equal(result.nPolls, 82);
  for (const id of ["A", "B"]) {
    assert.ok(result.intervals[id]);
    assert.ok(result.intervals[id].low < result.point[id]);
    assert.ok(result.intervals[id].high > result.point[id]);
    assert.ok(result.intervals[id].high - result.intervals[id].low < 0.1);
  }
});
