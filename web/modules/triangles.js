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

export function parallelogramCells(count) {
  let best = null;
  for (let cols = 1; cols <= count; cols += 1) {
    const rows = Math.max(1, Math.ceil(count / (2 * cols)));
    const capacity = 2 * rows * cols;
    const score = capacity - count + 0.15 * Math.abs(rows - cols);
    if (!best || score < best.score) best = { rows, cols, score };
  }
  const { rows, cols } = best;
  const cells = [];
  for (let row = 0; row < rows; row += 1) {
    const flip = row % 2 === 1;
    const y = row * HEIGHT;
    for (let col = 0; col < cols; col += 1) {
      const x = col + row * 0.5;
      if (!flip) {
        cells.push({ points: [[x, y + HEIGHT], [x + 1, y + HEIGHT], [x + 0.5, y]], cx: x + 0.5, cy: y + HEIGHT / 3 });
        cells.push({ points: [[x + 0.5, y], [x + 1.5, y], [x + 1, y + HEIGHT]], cx: x + 1, cy: y + (2 * HEIGHT) / 3 });
      } else {
        cells.push({ points: [[x, y], [x + 1, y], [x + 0.5, y + HEIGHT]], cx: x + 0.5, cy: y + (2 * HEIGHT) / 3 });
        cells.push({ points: [[x + 0.5, y + HEIGHT], [x + 1.5, y + HEIGHT], [x + 1, y]], cx: x + 1, cy: y + HEIGHT / 3 });
      }
    }
  }
  return cells.slice(0, count);
}

export function cellBounds(cells) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const cell of cells) {
    for (const [x, y] of cell.points) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

function translateCells(cells, x, y) {
  return cells.map((cell) => ({
    points: cell.points.map(([px, py]) => [px + x, py + y]),
    cx: cell.cx + x,
    cy: cell.cy + y,
  }));
}

export function hexClusterCells(count) {
  const full = Math.floor(count / 6);
  const remainder = count % 6;
  const tile = hexagonCells(1);
  const cells = [];
  for (let index = 0; index < full; index += 1) {
    const x = index * 1.5;
    const y = (index % 2) * (Math.sqrt(3) / 2);
    cells.push(...translateCells(tile, x, y));
  }
  if (remainder > 0) {
    const x = full * 1.5;
    const y = (full % 2) * (Math.sqrt(3) / 2);
    const partial = [...tile].sort((left, right) => right.cx - left.cx);
    cells.push(...translateCells(partial.slice(0, remainder), x, y));
  }
  return cells;
}
