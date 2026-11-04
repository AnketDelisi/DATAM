import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { medianSample } from "./aggregate.js";
import {
  actualFor,
  entitiesFor,
  errorSeries,
  finalSummary,
  leaveOneOut,
  pollsterLeaderboard,
  preparePolls,
} from "./backtest.js";

const pollPayload = JSON.parse(
  readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
);
const parliamentData = JSON.parse(
  readFileSync(new URL("../data/parliament_2023.json", import.meta.url), "utf8")
);

test("pollster leaderboard ranks the closer final poll higher", () => {
  const entities = ["A", "B"];
  const actual = { A: 0.5, B: 0.5 };
  const polls = [
    {
      pollster: "Good",
      field_end: "2023-05-01",
      results: { A: 0.5, B: 0.5 },
    },
    {
      pollster: "Bad",
      field_end: "2023-05-01",
      results: { A: 0.7, B: 0.3 },
    },
  ];
  const board = pollsterLeaderboard(polls, entities, actual, "2023-05-02");
  assert.equal(board[0].pollster, "Good");
  assert.ok(board[0].mae < board[1].mae);
});

test("leave-one-out finds the influential pollster", () => {
  const entities = ["A", "B"];
  const polls = [
    {
      pollster: "Good",
      field_end: "2023-05-01",
      results: { A: 0.5, B: 0.5 },
    },
    {
      pollster: "Bad",
      field_end: "2023-05-02",
      results: { A: 0.7, B: 0.3 },
    },
  ];
  const rows = leaveOneOut(polls, entities, "2023-05-02", {
    halfLifeDays: 28,
    normalize: true,
  });
  assert.equal(rows[0].pollster, "Bad");
  assert.ok(rows[0].maxAbs > 0);
});

test("2023 presidential backtest has usable error and robustness rows", () => {
  const race = "presidentFirst";
  const entities = entitiesFor(race);
  const polls = preparePolls(pollPayload, race);
  const actual = actualFor(parliamentData, race);
  const options = {
    halfLifeDays: 28,
    normalize: true,
    houseEffects: false,
    defaultSample: medianSample(polls),
  };
  const summary = finalSummary(polls, entities, actual, "2023-05-14", options);
  assert.equal(summary.nPolls, 82);
  assert.ok(summary.mae > 0.01 && summary.mae < 0.04);
  assert.equal(summary.rows.length, 4);

  const board = pollsterLeaderboard(polls, entities, actual, "2023-05-14");
  assert.equal(board.length, 30);
  assert.ok(board[0].mae <= board[board.length - 1].mae);

  const loo = leaveOneOut(polls, entities, "2023-05-14", options);
  assert.equal(loo.length, 30);
  assert.ok(loo[0].maxAbs > 0);

  const series = errorSeries(
    polls,
    entities,
    actual,
    "2023-03-15",
    "2023-05-14",
    options
  );
  assert.ok(series.length > 50);
  assert.equal(series[series.length - 1].date, "2023-05-14");
});
