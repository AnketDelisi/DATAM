export function createHemicycle(svg, total = 600) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const WIDTH = 600;
  const HEIGHT = 320;
  const blockCount = total >= 600 ? 2 : 1;
  const perBlock = Math.ceil(total / blockCount);
  const rows = Math.max(1, Math.ceil((Math.sqrt(8 * perBlock + 1) - 1) / 2));
  const size = 5;
  const spacingX = size * 1.8;
  const spacingY = size * 1.55;
  const gap = 28;
  const blockWidth = (rows - 1) * spacingX;
  const totalWidth = blockCount * blockWidth + (blockCount - 1) * gap;
  const startX = (WIDTH - totalWidth) / 2 + blockWidth / 2;
  const topY = (HEIGHT - 62 - (rows - 1) * spacingY) / 2 + 18;

  const positions = [];
  let remaining = total;
  for (let block = 0; block < blockCount; block += 1) {
    const blockCenter = startX + block * (blockWidth + gap);
    for (let row = 1; row <= rows && remaining > 0; row += 1) {
      const count = Math.min(row, remaining);
      const rowWidth = (count - 1) * spacingX;
      for (let col = 0; col < count; col += 1) {
        positions.push({
          block,
          row,
          col,
          x: blockCenter - rowWidth / 2 + col * spacingX,
          y: topY + (row - 1) * spacingY,
        });
        remaining -= 1;
      }
    }
  }
  positions.sort((a, b) => a.row - b.row || a.col - b.col || a.block - b.block);

  const triangle = (d) =>
    `M${d.x},${d.y - size} L${d.x + size * 0.9},${d.y + size * 0.75} L${d.x - size * 0.9},${d.y + size * 0.75} Z`;

  const group = root.append("g").attr("class", "hemicycle-seats");
  const shapes = group
    .selectAll("path")
    .data(positions)
    .join("path")
    .attr("d", triangle)
    .attr("fill", "#d7dbe0")
    .attr("stroke", "#fffdf8")
    .attr("stroke-width", 0.45);

  root
    .append("text")
    .attr("x", WIDTH / 2)
    .attr("y", HEIGHT - 12)
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
