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
  const cell = 11;
  const midRadius = (innerRadius + outerRadius) / 2;
  const candidates = [];

  for (let y = centerY - outerRadius; y <= centerY; y += cell) {
    for (let x = centerX - outerRadius; x <= centerX + outerRadius; x += cell) {
      const radius = Math.hypot(x + cell / 2 - centerX, y + cell / 2 - centerY);
      if (radius + cell * 0.71 > outerRadius) continue;
      if (radius - cell * 0.71 < innerRadius) continue;
      if (y + cell > centerY) continue;
      candidates.push({ x, y, radius });
    }
  }

  candidates.sort(
    (left, right) =>
      Math.abs(left.radius - midRadius) - Math.abs(right.radius - midRadius)
  );
  const seats = candidates.slice(0, total);
  seats.sort((left, right) => left.y - right.y || left.x - right.x);

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("rect")
    .data(seats)
    .join("rect")
    .attr("class", "seat-square")
    .attr("x", (seat) => seat.x + 0.5)
    .attr("y", (seat) => seat.y + 0.5)
    .attr("width", cell - 1)
    .attr("height", cell - 1)
    .attr("rx", 1)
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.35);

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
