import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { parliamentAggregate, presidentAggregate } from "./poll_preset.js";

const pollPayload = JSON.parse(
  readFileSync(new URL("../data/polls_2023.json", import.meta.url), "utf8")
);

test("presidential preset is the 2023 first-round aggregate", () => {
  const shares = presidentAggregate(pollPayload, 1);
  assert.ok(shares.A > 0.44 && shares.A < 0.49);
  assert.ok(shares.B > 0.44 && shares.B < 0.49);
  assert.ok(shares.C > 0.02 && shares.C < 0.04);
  assert.ok(shares.D > 0.02 && shares.D < 0.05);
});

test("parliamentary preset uses the main party shares", () => {
  const shares = parliamentAggregate(pollPayload);
  assert.ok(shares.P9 > 0.35 && shares.P9 < 0.39);
  assert.ok(shares.P21 > 0.26 && shares.P21 < 0.30);
  assert.ok(shares.OTHER > 0.02 && shares.OTHER < 0.05);
});
