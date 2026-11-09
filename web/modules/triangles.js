const HEIGHT = Math.sqrt(3) / 2;

export function triangleCells(side) {
  const cells = [];
  for (let row = 0; row < side; row += 1) {
    const y = row * HEIGHT;
    for (let index = 0; index <= row; index += 1) {
      const x = index - row / 2;
      cells.push({
        points: [
          [x, y],
          [x - 0.5, y + HEIGHT],
          [x + 0.5, y + HEIGHT],
        ],
        cx: x,
        cy: y + HEIGHT / 3,
      });
    }
    for (let index = 0; index < row; index += 1) {
      const x = index - (row - 1) / 2;
      cells.push({
        points: [
          [x - 0.5, y],
          [x + 0.5, y],
          [x, y + HEIGHT],
        ],
        cx: x,
        cy: y + (2 * HEIGHT) / 3,
      });
    }
  }
  return cells;
}

export function rotateCells(cells, angle) {
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return cells.map((cell) => ({
    points: cell.points.map(([x, y]) => [
      x * cosine - y * sine,
      x * sine + y * cosine,
    ]),
    cx: cell.cx * cosine - cell.cy * sine,
    cy: cell.cx * sine + cell.cy * cosine,
  }));
}

export function hexagonCells(side) {
  const cells = [];
  for (let sector = 0; sector < 6; sector += 1) {
    cells.push(
      ...rotateCells(triangleCells(side), (sector * Math.PI) / 3)
    );
  }
  return cells;
}

export function cellPath(cell, scale = 1, offsetX = 0, offsetY = 0) {
  const points = cell.points.map(([x, y]) => [
    offsetX + x * scale,
    offsetY + y * scale,
  ]);
  return `M${points[0][0]},${points[0][1]} L${points[1][0]},${points[1][1]} L${points[2][0]},${points[2][1]} Z`;
}
