export function createHemicycle(svg, total = 600) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const WIDTH = 600;
  const HEIGHT = 320;
  const centerX = WIDTH / 2;
  const centerY = 298;
  const innerRadius = 92;
  const outerRadius = 264;
  const rowCount = 18;
  const band = (outerRadius - innerRadius) / (rowCount - 1);
  const radii = Array.from(
    { length: rowCount },
    (_, index) => innerRadius + index * band
  );
  const weightTotal = radii.reduce((sum, radius) => sum + radius, 0);
  const counts = radii.map((radius) =>
    Math.max(1, Math.round((total * radius) / weightTotal))
  );
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
  for (let row = 0; row < rowCount; row += 1) {
    const radius = radii[row];
    const count = counts[row];
    const step = Math.PI / count;
    const chord = (Math.PI * radius) / count;
    const size = Math.max(3.4, Math.min(8.2, band * 0.82, chord * 0.58));
    for (let index = 0; index < count; index += 1) {
      const angle = Math.PI + (index + 0.5) * step;
      seats.push({
        angle,
        row,
        x: centerX + radius * Math.cos(angle) - size / 2,
        y: centerY + radius * Math.sin(angle) - size / 2,
        size,
      });
    }
  }
  seats.sort((left, right) => left.angle - right.angle || left.row - right.row);

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("rect")
    .data(seats)
    .join("rect")
    .attr("class", "seat-square")
    .attr("x", (seat) => seat.x)
    .attr("y", (seat) => seat.y)
    .attr("width", (seat) => seat.size)
    .attr("height", (seat) => seat.size)
    .attr("rx", 1)
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
      for (let index = 0; index < count; index += 1) order.push(party.id);
    }

    shapes.attr("fill", (_, index) => {
      const id = order[index];
      return id ? colors.get(id) || "#9e9e9e" : "#d7dbe0";
    });
  }

  return { update };
}
