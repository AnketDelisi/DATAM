import assert from "node:assert/strict";
import test from "node:test";

import { hexagonCells, triangleCells } from "./triangles.js";

test("triangle grid has a square number of cells", () => {
  assert.equal(triangleCells(1).length, 1);
  assert.equal(triangleCells(2).length, 4);
  assert.equal(triangleCells(10).length, 100);
});

test("hexagon of side 10 has 600 seats", () => {
  assert.equal(hexagonCells(10).length, 600);
});

test("each cell is a closed triangle path", () => {
  const path = triangleCells(1)[0];
  assert.equal(path.points.length, 3);
  assert.equal(path.points[0][1], 0);
  assert.ok(path.points[1][1] > 0);
});
