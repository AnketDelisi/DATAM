export function createHemicycle(svg, total = 600) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const WIDTH = 600;
  const HEIGHT = 320;
  const centerX = WIDTH / 2;
  const centerY = 298;
  const innerRadius = 92;
  const outerRadius = 266;
  const rowCount = 18;
  const radii = Array.from(
    { length: rowCount },
    (_, index) => innerRadius + ((outerRadius - innerRadius) * index) / (rowCount - 1)
  );
  const weightTotal = radii.reduce((sum, radius) => sum + radius, 0);
  const counts = radii.map((radius) => Math.max(1, Math.round((total * radius) / weightTotal)));
  let remaining = total - counts.reduce((sum, count) => sum + count, 0);
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
  const band = (outerRadius - innerRadius) / Math.max(1, rowCount - 1);
  verdict: for (let row = 0; row < rowCount; row += 1) {
    const radius = radii[row];
    const count = counts[row];
    const step = Math.PI / count;
    for (let index = 0; index < count; index += 1) {
      const angle = Math.PI + (index + 0.5) * step;
      const size = Math.min(band * 1.05, (Math.PI * radius) / count * 0.52);
      const tipRadius = radius - size * 0.62;
      const baseRadius = radius + size * 0.48;
      const tangentX = -Math.sin(angle);
      const tangentY = Math.cos(angle);
      const tip = [
        centerX + tipRadius * Math.cos(angle),
        centerY + tipRadius * Math.sin(angle),
      ];
      const base = [
        [
          centerX + baseRadius * Math.cos(angle) + tangentX * size * 0.58,
          centerY + baseRadius * Math.sin(angle) + tangentY * size * 0.58,
        ],
        [
          centerX + baseRadius * Math.cos(angle) - tangentX * size * 0.58,
          centerY + baseRadius * Math.sin(angle) - tangentY * size * 0.58,
        ],
      ];
      seats.push({
        angle,
        row,
        points: [tip, base[0], base[1]],
      });
      if (seats.length === total) break verdict;
    }
  }
  seats.sort((left, right) => left.angle - right.angle || left.row - right.row);

  const pathFor = (seat) =>
    `M${seat.points[0][0]},${seat.points[0][1]} L${seat.points[1][0]},${seat.points[1][1]} L${seat.points[2][0]},${seat.points[2][1]} Z`;

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("path")
    .data(seats)
    .join("path")
    .attr("d", pathFor)
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.4);

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
