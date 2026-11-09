import { cellPath, hexagonCells, triangleCells } from "./triangles.js";

export function createHemicycle(svg, total = 600) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const WIDTH = 600;
  const HEIGHT = 320;
  const side = total === 600 ? 10 : Math.ceil(Math.sqrt(total));
  const cells = total === 600 ? hexagonCells(side) : triangleCells(side).slice(0, total);
  const scale = total === 600 ? 13.5 : Math.min(42, 240 / side);
  const centerX = WIDTH / 2;
  const centerY = 142;
  const localCenterY = total === 600 ? 0 : (side * Math.sqrt(3)) / 4;
  const ordered = [...cells].sort(
    (left, right) => left.cx - right.cx || left.cy - right.cy
  );

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("path")
    .data(ordered)
    .join("path")
    .attr("d", (cell) =>
      cellPath(cell, scale, centerX, centerY - localCenterY * scale)
    )
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.45);

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
