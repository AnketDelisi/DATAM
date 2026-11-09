import { cellBounds, cellPath, hexClusterCells } from "./triangles.js";

export function createSeatCartogram(svg) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  const WIDTH = 1200;
  const HEIGHT = 520;
  root.attr("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);

  function update(provinces, parties) {
    root.selectAll("*").remove();
    const nodes = [...provinces.values()].map((province) => ({
      name: province.name,
      seats: province.seats || 0,
      scenario: province.scenario_seats || {},
    }));
    const tree = d3
      .hierarchy({ children: nodes })
      .sum((node) => node.seats || 0);
    d3.treemap()
      .size([WIDTH, HEIGHT])
      .paddingInner(2)
      .paddingOuter(2)
      .round(true)(tree);

    const colors = new Map(parties.map((party) => [party.id, party.color]));
    const sorted = [...parties].sort(
      (a, b) => a.seat_order - b.seat_order || a.id.localeCompare(b.id)
    );
    const group = root.append("g");

    for (const leaf of tree.leaves()) {
      const data = leaf.data;
      const width = leaf.x1 - leaf.x0;
      const height = leaf.y1 - leaf.y0;
      if (width < 2 || height < 2 || !data.seats) continue;
      const tile = group
        .append("g")
        .attr("transform", `translate(${leaf.x0},${leaf.y0})`);
      tile
        .append("rect")
        .attr("width", width)
        .attr("height", height)
        .attr("fill", "none")
        .attr("stroke", "#d5d1c4")
        .attr("stroke-width", 0.8);
      tile
        .append("title")
        .text(`${data.name}: ${data.seats} sandalye`);

      const cells = hexClusterCells(data.seats);
      const box = cellBounds(cells);
      const header = width > 54 && height > 24 ? 12 : 3;
      const scale = Math.min(
        (width - 6) / Math.max(1, box.width),
        (height - header - 6) / Math.max(1, box.height)
      );
      const offsetX = (width - box.width * scale) / 2 - box.minX * scale;
      const offsetY =
        header + (height - header - box.height * scale) / 2 - box.minY * scale;

      const partyOrder = [];
      for (const party of sorted) {
        const count = data.scenario[party.id] || 0;
        for (let index = 0; index < count; index += 1) {
          partyOrder.push(party.id);
        }
      }
      const cellsGroup = tile
        .append("g")
        .attr("transform", `translate(${offsetX},${offsetY})`);
      cells.forEach((cell, index) => {
        cellsGroup
          .append("path")
          .attr("d", cellPath(cell, scale))
          .attr("fill", colors.get(partyOrder[index]) || "#d7dbe0")
          .attr("stroke", "#fffdf8")
          .attr("stroke-width", 0.25);
      });

      if (header > 3) {
        tile
          .append("text")
          .attr("x", 4)
          .attr("y", 9)
          .attr("fill", "#33332d")
          .attr("font-size", Math.min(10, Math.max(7, width / 9)))
          .attr("font-weight", 700)
          .text(`${data.name} ${data.seats}`);
      }
    }
  }

  return { update };
}
