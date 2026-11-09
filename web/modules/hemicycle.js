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
  const tileScale = 18;
  const tileCells = hexagonCells(1);
  const tileCount = Math.round(total / 6);
  const horizontal = 1.5 * tileScale;
  const vertical = Math.sqrt(3) * tileScale;
  const midRadius = (innerRadius + outerRadius) / 2;

  const candidates = [];
  for (let column = -40; column <= 40; column += 1) {
    const x = centerX + column * horizontal;
    for (let row = -40; row <= 40; row += 1) {
      const y =
        centerY + row * vertical + (Math.abs(column) % 2 ? vertical / 2 : 0);
      if (y > centerY) continue;
      const radius = Math.hypot(x - centerX, y - centerY);
      if (radius < innerRadius || radius > outerRadius) continue;
      if (y + (tileScale * Math.sqrt(3)) / 2 > centerY) continue;
      let angle = Math.atan2(y - centerY, x - centerX);
      if (angle < 0) angle += Math.PI * 2;
      candidates.push({ x, y, radius, angle });
    }
  }
  candidates.sort(
    (left, right) =>
      Math.abs(left.radius - midRadius) - Math.abs(right.radius - midRadius)
  );
  const tiles = candidates.slice(0, tileCount);
  tiles.sort((left, right) => left.angle - right.angle || left.y - right.y);

  const seats = [];
  for (const tile of tiles) {
    for (const cell of tileCells) {
      seats.push({
        angle: tile.angle,
        radius: tile.radius,
        path: cellPath(cell, tileScale, tile.x, tile.y),
      });
    }
  }
  const clipId = "hemicycle-half-donut";
  root
    .append("defs")
    .append("clipPath")
    .attr("id", clipId)
    .append("path")
    .attr(
      "d",
      `M${centerX - outerRadius},${centerY} A${outerRadius},${outerRadius} 0 0 1 ${centerX + outerRadius},${centerY} L${centerX + innerRadius},${centerY} A${innerRadius},${innerRadius} 0 0 0 ${centerX - innerRadius},${centerY} Z`
    );

  const group = root
    .append("g")
    .attr("class", "hemicycle-seats")
    .attr("clip-path", `url(#${clipId})`);
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
