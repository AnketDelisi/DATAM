import {
  RACES,
  actualFor,
  entitiesFor,
  errorSeries,
  finalSummary,
  leaveOneOut,
  pollsterLeaderboard,
  preparePolls,
} from "./modules/backtest.js";
import { medianSample } from "./modules/aggregate.js";
import { formatInt, formatPct } from "./modules/format.js";
import { bootstrapAggregate } from "./modules/uncertainty.js";

const TR_MONTHS = [
  "Oca",
  "Şub",
  "Mar",
  "Nis",
  "May",
  "Haz",
  "Tem",
  "Ağu",
  "Eyl",
  "Eki",
  "Kas",
  "Ara",
];
const ppFormat = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const ciFormat = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const state = {
  data: null,
  pollData: null,
  raceKey: "presidentFirst",
  halfLife: 28,
  houseEffects: false,
  normalize: true,
  meta: new Map(),
};

function $(id) {
  return document.getElementById(id);
}

function formatDateShort(value) {
  const date = value instanceof Date ? value : new Date(`${value}T00:00:00Z`);
  return `${date.getUTCDate()} ${TR_MONTHS[date.getUTCMonth()]}`;
}

function formatDateLong(value) {
  const date = value instanceof Date ? value : new Date(`${value}T00:00:00Z`);
  return `${date.getUTCDate()} ${TR_MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

function formatPp(value) {
  if (value == null || !Number.isFinite(value)) return "–";
  return `${ppFormat.format(value * 100)} puan`;
}

function formatSignedPp(value) {
  if (value == null || !Number.isFinite(value)) return "–";
  const points = value * 100;
  if (Math.abs(points) < 0.05) return "0,0 puan";
  return `${points > 0 ? "+" : ""}${ppFormat.format(points)} puan`;
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character]
  );
}

function entityMeta(id) {
  if (id === "OTHER") return { short: "Diğer", color: "#9e9e9e" };
  return state.meta.get(id) || { short: id, color: "#9e9e9e" };
}

async function main() {
  const [data, pollData] = await Promise.all([
    fetch("./data/parliament_2023.json").then((response) => {
      if (!response.ok) throw new Error(`data ${response.status}`);
      return response.json();
    }),
    fetch("./data/polls_2023.json").then((response) => {
      if (!response.ok) throw new Error(`polls ${response.status}`);
      return response.json();
    }),
  ]);
  state.data = data;
  state.pollData = pollData;
  state.meta = new Map(
    [...data.president.candidates, ...data.parties].map((item) => [
      item.id,
      item,
    ])
  );

  buildRaceSwitch();
  readUrl();
  attachControls();
  setGeneratedAt();
  applyRace(state.raceKey);
}

function buildRaceSwitch() {
  $("race-switch").innerHTML = Object.values(RACES)
    .map(
      (race) =>
        `<button type="button" class="race-button" data-race="${race.key}">${race.label}</button>`
    )
    .join("");
  for (const button of document.querySelectorAll(".race-button")) {
    button.addEventListener("click", () => applyRace(button.dataset.race));
  }
}

function updateRaceButtons() {
  for (const button of document.querySelectorAll(".race-button")) {
    button.classList.toggle("active", button.dataset.race === state.raceKey);
  }
}

function applyRace(key) {
  if (!RACES[key]) return;
  state.raceKey = key;
  updateRaceButtons();
  render();
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  const race = params.get("race");
  if (race && RACES[race]) state.raceKey = race;
  const halfLife = Number(params.get("hl"));
  if (Number.isFinite(halfLife)) {
    state.halfLife = Math.min(60, Math.max(7, halfLife));
  }
  if (params.has("he")) state.houseEffects = params.get("he") === "1";
  if (params.has("norm")) state.normalize = params.get("norm") !== "0";
}

function attachControls() {
  $("half-life").value = state.halfLife;
  $("half-life-value").textContent = `${state.halfLife} gün`;
  $("house-effects").checked = state.houseEffects;
  $("normalize").checked = state.normalize;

  $("half-life").addEventListener("input", (event) => {
    state.halfLife = Number(event.target.value);
    $("half-life-value").textContent = `${state.halfLife} gün`;
    render();
  });
  $("house-effects").addEventListener("change", (event) => {
    state.houseEffects = event.target.checked;
    render();
  });
  $("normalize").addEventListener("change", (event) => {
    state.normalize = event.target.checked;
    render();
  });
  $("reset").addEventListener("click", () => {
    state.halfLife = 28;
    state.houseEffects = false;
    state.normalize = true;
    $("half-life").value = 28;
    $("half-life-value").textContent = "28 gün";
    $("house-effects").checked = false;
    $("normalize").checked = true;
    render();
  });
}

function render() {
  const race = RACES[state.raceKey];
  const entities = entitiesFor(state.raceKey);
  const polls = preparePolls(state.pollData, state.raceKey);
  const actual = actualFor(state.data, state.raceKey);
  const options = {
    halfLifeDays: state.halfLife,
    normalize: state.normalize,
    houseEffects: state.houseEffects,
    defaultSample: medianSample(polls),
  };
  const summary = finalSummary(polls, entities, actual, race.electionDay, options);
  const uncertainty = bootstrapAggregate(
    polls,
    entities,
    race.electionDay,
    options,
    400
  );
  const board = pollsterLeaderboard(polls, entities, actual, race.electionDay);
  const loo = leaveOneOut(polls, entities, race.electionDay, options);
  const start = polls.reduce(
    (min, poll) => (poll.field_end < min ? poll.field_end : min),
    race.electionDay
  );
  const series = errorSeries(polls, entities, actual, start, race.electionDay, options);

  drawErrorChart(race, series, entities, summary);
  updateFinalTable(race, summary, uncertainty);
  updateLeaderboard(race, board);
  updateLoo(race, loo);
  updateMeta(race, summary, board);
  updateUrl();
}

function drawErrorChart(race, series, entities, summary) {
  const d3 = globalThis.d3;
  const svg = d3.select("#error-chart");
  svg.selectAll("*").remove();
  const legend = $("chart-legend");

  if (!series.length) {
    svg
      .append("text")
      .attr("x", 450)
      .attr("y", 200)
      .attr("text-anchor", "middle")
      .attr("class", "chart-empty")
      .text("Hesaplanacak anket yok.");
    legend.innerHTML = "";
    return;
  }

  const display = [...entities]
    .sort(
      (a, b) =>
        (summary.aggregate.shares[b] || 0) - (summary.aggregate.shares[a] || 0)
    )
    .slice(0, race.key === "presidentFirst" ? 4 : 5);

  const width = 900;
  const height = 420;
  const margin = { top: 22, right: 120, bottom: 34, left: 48 };
  const start = new Date(`${series[0].date}T00:00:00Z`);
  const end = new Date(`${race.electionDay}T00:00:00Z`);
  const x = d3
    .scaleTime()
    .domain([start, end])
    .range([margin.left, width - margin.right]);

  const maxError = Math.max(
    ...series.map((point) => point.mae * 100),
    ...series.flatMap((point) =>
      display.map((id) => (point.errors[id] == null ? 0 : point.errors[id] * 100))
    )
  );
  const yMax = Math.min(30, Math.max(5, Math.ceil((maxError * 1.1) / 5) * 5));
  const y = d3
    .scaleLinear()
    .domain([0, yMax])
    .range([height - margin.bottom, margin.top]);

  const plot = svg.append("g");
  const ticks = d3.range(0, yMax + 1, 5);
  for (const tick of ticks) {
    plot
      .append("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(tick))
      .attr("y2", y(tick))
      .attr("class", "chart-grid");
  }

  plot
    .append("g")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .attr("class", "chart-axis")
    .call(
      d3
        .axisBottom(x)
        .ticks(d3.timeDay.every(7))
        .tickFormat((value) => formatDateShort(value))
    );

  plot
    .append("g")
    .attr("transform", `translate(${margin.left},0)`)
    .attr("class", "chart-axis")
    .call(
      d3
        .axisLeft(y)
        .tickValues(ticks)
        .tickFormat((value) => `${value}`)
    );

  const line = d3
    .line()
    .defined((point) => point.value != null)
    .x((point) => x(new Date(`${point.date}T00:00:00Z`)))
    .y((point) => y(point.value))
    .curve(d3.curveMonotoneX);

  for (const id of display) {
    const meta = entityMeta(id);
    const values = series.map((point) => ({
      date: point.date,
      value: point.errors[id] == null ? null : point.errors[id] * 100,
    }));
    plot
      .append("path")
      .datum(values)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", meta.color)
      .attr("stroke-width", 1.8)
      .attr("opacity", 0.75);
  }

  plot
    .append("path")
    .datum(series.map((point) => ({ date: point.date, value: point.mae * 100 })))
    .attr("d", line)
    .attr("fill", "none")
    .attr("stroke", "#111827")
    .attr("stroke-width", 3);

  const last = series[series.length - 1];
  plot
    .append("circle")
    .attr("cx", x(new Date(`${last.date}T00:00:00Z`)))
    .attr("cy", y(last.mae * 100))
    .attr("r", 4)
    .attr("fill", "#111827");

  legend.innerHTML =
    `<span class="legend-item"><i style="background:#111827"></i>MAE</span>` +
    display
      .map((id) => {
        const meta = entityMeta(id);
        return `<span class="legend-item"><i style="background:${meta.color}"></i>${meta.short}</span>`;
      })
      .join("");
}

function updateFinalTable(race, summary, uncertainty) {
  $("final-metrics").textContent = `MAE ${formatPp(summary.mae)} · ${
    summary.nPolls
  } anket · son anket ${
    summary.lastPoll ? formatDateLong(summary.lastPoll) : "–"
  }`;

  const rows = [...summary.rows]
    .sort((a, b) => (b.aggregate || 0) - (a.aggregate || 0))
    .map((row) => {
      const meta = entityMeta(row.id);
      const className =
        row.error == null ? "" : row.error > 0 ? "neg" : row.error < 0 ? "pos" : "";
      const interval = uncertainty?.intervals?.[row.id];
      const ci = interval
        ? `${ciFormat.format(interval.low * 100)}–${ciFormat.format(
            interval.high * 100
          )}`
        : "";
      return `<tr>
        <td><span class="swatch" style="background:${meta.color}"></span>${meta.short}</td>
        <td class="num">${
          row.aggregate == null ? "–" : formatPct(row.aggregate * 100)
        }${ci ? `<div class="ci">${ci}</div>` : ""}</td>
        <td class="num muted">${
          row.actual == null ? "–" : formatPct(row.actual * 100)
        }</td>
        <td class="num ${className}">${formatSignedPp(row.error)}</td>
      </tr>`;
    })
    .join("");
  $("final-table").innerHTML = rows;
}

function updateLeaderboard(race, board) {
  $("leaderboard-note").textContent = `${board.length} pollster`;
  $("leaderboard-table").innerHTML = board
    .map((row) => {
      const biasClass = row.bias > 0 ? "neg" : row.bias < 0 ? "pos" : "";
      return `<tr>
        <td>${escapeHtml(row.pollster)}</td>
        <td class="num">${formatInt(row.nPolls)}</td>
        <td class="num">${formatDateShort(row.lastPoll)}</td>
        <td class="num">${formatPp(row.mae)}</td>
        <td class="num ${biasClass}">${formatSignedPp(row.bias)}</td>
      </tr>`;
    })
    .join("");
}

function updateLoo(race, loo) {
  $("loo-table").innerHTML = loo
    .map((row) => {
      const meta = entityMeta(row.entity);
      const className = row.delta > 0 ? "pos" : row.delta < 0 ? "neg" : "";
      return `<tr>
        <td>${escapeHtml(row.pollster)}</td>
        <td class="num">${formatInt(row.nPolls)}</td>
        <td class="num ${className}">${formatSignedPp(row.delta)}</td>
        <td>${meta.short}</td>
      </tr>`;
    })
    .join("");
}

function updateMeta(race, summary, board) {
  $("backtest-summary").textContent = `${summary.nPolls} anket · ${
    board.length
  } pollster · MAE ${formatPp(summary.mae)}`;
  $("chart-subtitle").textContent = `${race.label} · mutlak hata (puan) · ${
    state.houseEffects ? "pollster düzeltmeli" : "ham"
  }`;
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("race", state.raceKey);
  params.set("hl", String(state.halfLife));
  params.set("he", state.houseEffects ? "1" : "0");
  params.set("norm", state.normalize ? "1" : "0");
  try {
    history.replaceState(null, "", `?${params.toString()}`);
  } catch {
    // file:// or a restricted context.
  }
}

function setGeneratedAt() {
  const value = state.pollData.meta?.generated_at || state.data.meta?.generated_at;
  if (!value) return;
  const formatted = new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
  $("generated-at").textContent = `Veri: ${formatted}`;
}

main().catch((error) => {
  console.error(error);
  const panel = document.querySelector(".chart-panel");
  if (panel) {
    panel.innerHTML = `<div class="error">Veri yüklenemedi: ${error.message}</div>`;
  }
});
