import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  allocateDistricts,
  dhondt,
  qualifyingParties,
} from "./allocate.js";

test("dhondt basic", () => {
  const result = dhondt({ A: 100, B: 50, C: 25 }, 3, new Set(["A", "B", "C"]));
  assert.deepEqual(result, { A: 2, B: 1, C: 0 });
});

test("threshold and alliance", () => {
  const qualified = qualifyingParties(
    { A: 70, B: 3, C: 27 },
    { X: ["B", "C"] },
    0.1
  );
  assert.deepEqual([...qualified].sort(), ["A", "B", "C"]);
});

test("2023 allocation matches the Python model", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/parliament_2023.json", import.meta.url), "utf8")
  );
  const result = allocateDistricts(
    data.districts,
    data.meta.alliances,
    data.meta.threshold
  );
  assert.equal(
    Object.values(result.seatsByParty).reduce((a, b) => a + b, 0),
    600
  );
  assert.equal(result.seatsByParty.P9, 266);
  assert.equal(result.seatsByParty.P11, 51);
  assert.equal(result.seatsByParty.P12, 62);
  assert.equal(result.seatsByParty.P21, 168);
  assert.equal(result.seatsByParty.P22, 44);
  assert.equal(result.seatsByParty.P10, 5);
  assert.equal(result.seatsByParty.P13, 4);
});
