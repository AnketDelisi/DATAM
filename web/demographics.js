import {
  REGION_COLORS,
  correlationsFor,
  domain,
  formatCorrelation,
  formatDemographic,
  formatMetric,
  formatOutcome,
  formatRegion,
  linearRegression,
  regionColor,
} from "./modules/demographics.js";
import { formatInt, normalizeName } from "./modules/format.js";

const state = {
  data: null,
  geojson: null,
  outcome: "CHP",
  demographic: "hh_5plus",
  mapMode: "demographic",
  viewMode: "simple",
};

function $(id) {
  return document.getElementById(id);
}

async function main() {
  const [data, geojson] = await Promise.all([
    fetch("./data/demographics.json").then((response) => {
      if (!response.ok) throw new Error(`demografi ${response.status}`);
      return response.json();
    }),
    fetch("./geo/tr-provinces.geojson").then((response) => {
      if (!response.ok) throw new Error(`harita ${response.status}`);
      return response.json();
    }),
  ]);
  state.data = data;
  state.geojson = geojson;

  const outcomes = state.data.meta.outcomes;
  const demographics = state.data.meta.demographics;
  if (!outcomes.includes(state.outcome)) state.outcome = outcomes[0];
  if (!demographics.includes(state.demographic)) state.demographic = demographics[0];

  const outcomeSelect = $("outcome");
  outcomeSelect.innerHTML = outcomes
    .map((key) => `<option value="${key}">${formatOutcome(key)}</option>`)
    .join("");
  outcomeSelect.value = state.outcome;

  const demographicSelect = $("demographic");
  demographicSelect.innerHTML = demographics
    .map((key) => `<option value="${key}">${formatDemographic(key)}</option>`)
    .join("");
  demographicSelect.value = state.demographic;

  readUrl();
  outcomeSelect.value = state.outcome;
  demographicSelect.value = state.demographic;

  outcomeSelect.addEventListener("change", (event) => {
    state.outcome = event.target.value;
    render();
  });
  demographicSelect.addEventListener("change", (event) => {
    state.demographic = event.target.value;
    render();
  });
  $("map-demographic").addEventListener("click", () => {
    state.mapMode = "demographic";
    render();
  });
  $("map-outcome").addEventListener("click", () => {
    state.mapMode = "outcome";
    render();
  });
  $("view-simple").addEventListener("click", () => {
    state.viewMode = "simple";
    render();
  });
  $("view-expert").addEventListener("click", () => {
    state.viewMode = "expert";
    render();
  });

  $("generated-at").textContent = state.data.meta.source;
  render();
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  const outcome = params.get("outcome");
  const demographic = params.get("demo");
  const mapMode = params.get("map");
  const view = params.get("view");
  if (outcome && state.data.meta.outcomes.includes(outcome)) state.outcome = outcome;
  if (demographic && state.data.meta.demographics.includes(demographic)) {
    state.demographic = demographic;
  }
  if (mapMode === "outcome" || mapMode === "demographic") state.mapMode = mapMode;
  if (view === "simple" || view === "expert") state.viewMode = view;
}

function selectedCorrelation() {
  return state.data.correlations.find(
    (row) => row.outcome === state.outcome && row.demographic === state.demographic
  );
}

function render() {
  document.body.dataset.view = state.viewMode;
  $("view-simple").classList.toggle("active", state.viewMode === "simple");
  $("view-expert").classList.toggle("active", state.viewMode === "expert");
  const rows = correlationsFor(state.data.correlations, state.outcome);
  renderStats(rows);
  renderScatter();
  renderTable(rows);
  renderMap();
  updateUrl();
}

function strengthLabel(value) {
  const absolute = Math.abs(value);
  if (absolute >= 0.7) return "Çok güçlü";
  if (absolute >= 0.5) return "Güçlü";
  if (absolute >= 0.3) return "Orta";
  if (absolute >= 0.15) return "Zayıf";
  return "Çok zayıf";
}

function directionLabel(value) {
  if (Math.abs(value) < 0.05) return "İlişki yok";
  return value > 0 ? "Aynı yönlü" : "Ters yönlü";
}

function groupMeans() {
  const rows = state.data.provinces
    .filter(
      (row) =>
        Number.isFinite(row[state.demographic]) &&
        Number.isFinite(row[state.outcome])
    )
    .sort((a, b) => b[state.demographic] - a[state.demographic]);
  const size = Math.max(5, Math.round(rows.length * 0.2));
  const average = (items) =>
    items.reduce((sum, row) => sum + row[state.outcome], 0) / items.length;
  return {
    top: average(rows.slice(0, size)),
    bottom: average(rows.slice(-size)),
  };
}

function renderStats(rows) {
  const selected = selectedCorrelation();
  const strongest = rows[0];
  let cards;
  if (state.viewMode === "simple" && selected) {
    const means = groupMeans();
    cards = [
      ["İlişki", strengthLabel(selected.pearson_r), directionLabel(selected.pearson_r)],
      ["Yüksek grup", formatMetric(state.outcome, means.top), "gösterge en yüksek %20"],
      ["Düşük grup", formatMetric(state.outcome, means.bottom), "gösterge en düşük %20"],
      ["İl", formatInt(selected.n), "gözlem"],
    ];
  } else {
    cards = [
      ["Pearson r", selected ? formatCorrelation(selected.pearson_r) : "–", ""],
      ["Partial r", selected ? formatCorrelation(selected.partial_r) : "–", "bölge + seçmen"],
      ["Ağırlıklı r", selected ? formatCorrelation(selected.weighted_r) : "–", "seçmen ağırlıklı"],
      ["n", selected ? formatInt(selected.n) : "–", "il"],
    ];
  }
  $("corr-stats").innerHTML = cards
    .map(
      ([label, value, note]) =>
        `<div class="stat"><span>${label}</span><strong>${value}</strong>${
          note ? `<small>${note}</small>` : ""
        }</div>`
    )
    .join("");

  $("plain-summary").innerHTML = selected
    ? `${formatDemographic(state.demographic)} yüksek olan illerde ` +
      `${formatOutcome(state.outcome)} daha ${
        selected.pearson_r >= 0 ? "yüksek" : "düşük"
      }. İlişki <strong>${strengthLabel(selected.pearson_r).toLowerCase()}</strong> ` +
      `ve ${directionLabel(selected.pearson_r).toLowerCase()}. ` +
      `<span class="muted">Bu nedensellik değildir.</span>`
    : "";

  $("scatter-subtitle").textContent = `${formatOutcome(state.outcome)} × ${formatDemographic(
    state.demographic
  )}`;
  $("table-note").textContent = strongest
    ? `En güçlü: ${formatDemographic(strongest.demographic)}`
    : "";
}

function renderScatter() {
  const d3 = globalThis.d3;
  const svg = d3.select("#scatter");
  svg.selectAll("*").remove();

  const width = 900;
  const height = 460;
  const margin = { top: 20, right: 24, bottom: 52, left: 66 };
  const points = state.data.provinces
    .map((province) => ({
      province: province.province,
      region: province.region,
      electorate: province.electorate,
      x: province[state.demographic],
      y: province[state.outcome],
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));

  if (!points.length) {
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", height / 2)
      .attr("text-anchor", "middle")
      .attr("class", "chart-empty")
      .text("Veri yok.");
    return;
  }

  const [x0, x1] = domain(points.map((point) => point.x));
  const [y0, y1] = domain(points.map((point) => point.y));
  const x = d3
    .scaleLinear()
    .domain([x0, x1])
    .nice()
    .range([margin.left, width - margin.right]);
  const y = d3
    .scaleLinear()
    .domain([y0, y1])
    .nice()
    .range([height - margin.bottom, margin.top]);

  const xTicks = x.ticks(6);
  const yTicks = y.ticks(6);
  const plot = svg.append("g");

  for (const tick of yTicks) {
    plot
      .append("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(tick))
      .attr("y2", y(tick))
      .attr("class", "chart-grid");
  }
  for (const tick of xTicks) {
    plot
      .append("line")
      .attr("x1", x(tick))
      .attr("x2", x(tick))
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("class", "chart-grid");
  }

  plot
    .append("g")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .attr("class", "chart-axis")
    .call(
      d3
        .axisBottom(x)
        .tickValues(xTicks)
        .tickFormat((value) => formatMetric(state.demographic, value, 0))
    );
  plot
    .append("g")
    .attr("transform", `translate(${margin.left},0)`)
    .attr("class", "chart-axis")
    .call(
      d3
        .axisLeft(y)
        .tickValues(yTicks)
        .tickFormat((value) => formatMetric(state.outcome, value, 0))
    );

  const maxElectorate = d3.max(points, (point) => point.electorate) || 1;
  const radius = (value) => 3 + 7 * Math.sqrt(value / maxElectorate);

  plot
    .selectAll("circle")
    .data(points)
    .join("circle")
    .attr("cx", (point) => x(point.x))
    .attr("cy", (point) => y(point.y))
    .attr("r", (point) => radius(point.electorate))
    .attr("fill", (point) => regionColor(point.region))
    .attr("opacity", 0.72)
    .attr("stroke", "#fff")
    .attr("stroke-width", 1)
    .append("title")
    .text(
      (point) =>
        `${point.province} · ${formatMetric(state.demographic, point.x)} · ` +
        `${formatMetric(state.outcome, point.y)} · ${formatInt(point.electorate)} seçmen`
    );

  const line = linearRegression(points);
  if (line) {
    plot
      .append("line")
      .attr("x1", x(x0))
      .attr("y1", y(line.slope * x0 + line.intercept))
      .attr("x2", x(x1))
      .attr("y2", y(line.slope * x1 + line.intercept))
      .attr("stroke", "#1b1b1b")
      .attr("stroke-width", 1.6)
      .attr("stroke-dasharray", "6 4")
      .attr("opacity", 0.8);
  }

  svg
    .append("text")
    .attr("x", (margin.left + width - margin.right) / 2)
    .attr("y", height - 8)
    .attr("text-anchor", "middle")
    .attr("class", "chart-axis")
    .text(formatDemographic(state.demographic));

  svg
    .append("text")
    .attr("transform", `translate(16,${margin.top + (height - margin.top - margin.bottom) / 2}) rotate(-90)`)
    .attr("text-anchor", "middle")
    .attr("class", "chart-axis")
    .text(formatOutcome(state.outcome));

  const regions = Object.keys(REGION_COLORS).filter((region) =>
    points.some((point) => point.region === region)
  );
  $("region-legend").innerHTML = regions
    .map(
      (region) =>
        `<span class="legend-item"><i style="background:${regionColor(region)}"></i>${formatRegion(
          region
        )}</span>`
    )
    .join("");
}

function renderTable(rows) {
  const simple = state.viewMode === "simple";
  $("corr-table-head").innerHTML = simple
    ? "<tr><th>Gösterge</th><th>İlişki</th></tr>"
    : "<tr><th>Gösterge</th><th>r</th><th>partial r</th><th>r̄</th></tr>";
  $("corr-table").innerHTML = rows
    .map(
      (row) => `<tr data-demographic="${row.demographic}" class="${
        row.demographic === state.demographic ? "selected" : ""
      }">
        <td>${formatDemographic(row.demographic)}</td>
        ${
          simple
            ? `<td><span class="strength ${row.pearson_r >= 0 ? "pos" : "neg"}">${strengthLabel(
                row.pearson_r
              )} ${directionLabel(row.pearson_r).toLowerCase()}</span></td>`
            : `<td class="num ${row.pearson_r >= 0 ? "pos" : "neg"}">${formatCorrelation(
                row.pearson_r
              )}</td>
        <td class="num">${formatCorrelation(row.partial_r)}</td>
        <td class="num">${formatCorrelation(row.weighted_r)}</td>`
        }
      </tr>`
    )
    .join("");

  for (const row of $("corr-table").querySelectorAll("tr")) {
    row.addEventListener("click", () => {
      state.demographic = row.dataset.demographic;
      $("demographic").value = state.demographic;
      render();
    });
  }
}

function renderMap() {
  const d3 = globalThis.d3;
  const svg = d3.select("#demo-map");
  svg.selectAll("*").remove();
  if (!state.geojson) return;

  const variable = state.mapMode === "outcome" ? state.outcome : state.demographic;
  const byKey = new Map(state.data.provinces.map((row) => [row.key, row]));
  const values = state.data.provinces
    .map((row) => row[variable])
    .filter((value) => Number.isFinite(value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const color = d3
    .scaleSequential(d3.interpolateRgb("#f7f7f2", "#1b1b1b"))
    .domain([min, max]);

  const projection = d3
    .geoConicConformal()
    .parallels([35, 45])
    .rotate([-35, 0])
    .fitExtent([[18, 12], [782, 368]], state.geojson);
  const path = d3.geoPath(projection);

  svg
    .append("g")
    .selectAll("path")
    .data(state.geojson.features)
    .join("path")
    .attr("d", path)
    .attr("fill", (feature) => {
      const key = normalizeName(feature.properties.shapeName);
      const value = byKey.get(key)?.[variable];
      return Number.isFinite(value) ? color(value) : "#dfe3e8";
    })
    .attr("stroke", "#fff")
    .attr("stroke-width", 0.6)
    .attr("vector-effect", "non-scaling-stroke")
    .append("title")
    .text((feature) => {
      const key = normalizeName(feature.properties.shapeName);
      const row = byKey.get(key);
      if (!row) return feature.properties.shapeName;
      return `${row.province} ? ${formatMetric(variable, row[variable])}`;
    });

  $("demo-map-legend").innerHTML =
    `<span>${formatMetric(variable, min)}</span><i></i><span>${formatMetric(
      variable,
      max
    )}</span>`;
  for (const [id, active] of [
    ["map-demographic", state.mapMode === "demographic"],
    ["map-outcome", state.mapMode === "outcome"],
  ]) {
    $(id).classList.toggle("active", active);
  }
  $("demo-map").setAttribute(
    "aria-label",
    `${formatDemographic(state.demographic)} / ${formatOutcome(state.outcome)} il haritas?`
  );
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("outcome", state.outcome);
  params.set("demo", state.demographic);
  params.set("map", state.mapMode);
  params.set("view", state.viewMode);
  try {
    history.replaceState(null, "", `?${params.toString()}`);
  } catch {
    // file:// or a restricted context.
  }
}

main().catch((error) => {
  console.error(error);
  const panel = document.querySelector(".chart-panel");
  if (panel) {
    panel.innerHTML = `<div class="error">Veri yüklenemedi: ${error.message}</div>`;
  }
});
