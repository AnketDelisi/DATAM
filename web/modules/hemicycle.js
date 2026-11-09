import { cellPath, hexagonCells } from "./triangles.js";

export function createHemicycle(svg, total = 600) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const WIDTH = 600;
  const HEIGHT = 320;
  const centerX = WIDTH / 2;
  const centerY = 298;
  const innerRadius = 88;
  const outerRadius = 252;
  const rowCount = 8;
  const tileCount = Math.round(total / 6);
  const tileCells = hexagonCells(1);
  const tileScale = 11.5;

  const radii = Array.from(
    { length: rowCount },
    (_, index) =>
      innerRadius + ((outerRadius - innerRadius) * index) / (rowCount - 1)
  );
  const weightTotal = radii.reduce((sum, radius) => sum + radius, 0);
  const counts = radii.map((radius) =>
    Math.max(1, Math.round((tileCount * radius) / weightTotal))
  );
  let remaining = tileCount - counts.reduce((sum, count) => sum + count, 0);
  let cursor = 0;
  while (remaining !== 0) {
    const index = cursor % rowCount;
    if (remaining > 0) {
      counts[index] += 1;
      remaining -= 1;
    } else if (counts[index] > 1) {
      counts[index] -= 1;
      remaining += 1;
    }
    cursor += 1;
  }

  const seats = [];
  for (let row = 0; row < rowCount; row += 1) {
    const radius = radii[row];
    const count = counts[row];
    const step = Math.PI / count;
    for (let tile = 0; tile < count; tile += 1) {
      const angle = Math.PI + (tile + 0.5) * step;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      for (const cell of tileCells) {
        seats.push({
          angle,
          row,
          path: cellPath(cell, tileScale, x, y),
        });
      }
    }
  }
  seats.sort((left, right) => left.angle - right.angle || left.row - right.row);

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("path")
    .data(seats)
    .join("path")
    .attr("d", (seat) => seat.path)
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.5);

  root
    .append("text")
    .attr("x", centerX)
    .attr("y", HEIGHT - 12)
    .attr("text-anchor", "middle")
    .attr("class", "hemicycle-caption")
    .text(`${total} sandalye`);

  const colors = new Map();

  function update(seatsByParty, parties) {
    colors.clear();
    for (const party of parties) colors.set(party.id, party.color);

    const order = [];
    const sorted = [...parties].sort(
      (a, b) => a.seat_order - b.seat_order || a.id.localeCompare(b.id)
    );
    for (const party of sorted) {
      const count = seatsByParty[party.id] || 0;
      for (let i = 0; i < count; i += 1) order.push(party.id);
    }

    shapes.attr("fill", (_, index) => {
      const id = order[index];
      return id ? colors.get(id) || "#9e9e9e" : "#d7dbe0";
    });
  }

  return { update };
}
