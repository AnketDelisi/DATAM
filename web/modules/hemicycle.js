export function createHemicycle(svg, total = 600, rows = 20, perRow = 30) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const cx = 300;
  const cy = 295;
  const inner = 110;
  const step = 9;
  const positions = [];

  for (let row = 0; row < rows; row += 1) {
    const radius = inner + row * step;
    for (let col = 0; col < perRow; col += 1) {
      const angle = ((col + 0.5) * Math.PI) / perRow;
      positions.push({
        angle,
        row,
        x: cx - radius * Math.cos(angle),
        y: cy - radius * Math.sin(angle),
      });
    }
  }

  positions.sort((a, b) => a.angle - b.angle || a.row - b.row);
  const seats = positions.slice(0, total);

  const triangle = (d) => {
    const size = 4.1;
    return `M${d.x},${d.y - size} L${d.x + size * 0.9},${d.y + size * 0.75} L${d.x - size * 0.9},${d.y + size * 0.75} Z`;
  };

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("path")
    .data(seats)
    .join("path")
    .attr("d", triangle)
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.45);

  root
    .append("text")
    .attr("x", cx)
    .attr("y", cy - 8)
    .attr("text-anchor", "middle")
    .attr("class", "hemicycle-caption")
    .text(`${total} sandalye`);

  const colors = new Map();

  function update(seatsByParty, parties) {
    colors.clear();
    for (const party of parties) colors.set(party.id, party.color);

    const ordered = [...parties].sort(
      (a, b) => a.seat_order - b.seat_order || a.id.localeCompare(b.id)
    );
    const order = [];
    for (const party of ordered) {
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
