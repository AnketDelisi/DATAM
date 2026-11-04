import {
  aggregateAt,
  buildTrend,
  medianSample,
  normalizePoll,
  toDate,
} from "./modules/aggregate.js";
import { formatInt, formatPct } from "./modules/format.js";
import { bootstrapAggregate } from "./modules/uncertainty.js";

const MAIN_PARTIES = ["P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24"];
const OTHER = "OTHER";
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
const ciFormat = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const state = {
  data: null,
  pollData: null,
  races: {},
  raceKey: "presidentFirst",
  halfLife: 28,
  cutoff: null,
  houseEffects: false,
  normalize: true,
  aggregate: null,
  trend: [],
  polls: [],
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

function formatSignedPct(value) {
  const points = value * 100;
  if (Math.abs(points) < 0.05) return "0,0%";
  return `${points > 0 ? "+" : ""}${formatPct(points)}`;
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

function currentRace() {
  return state.races[state.raceKey];
}

function entityMeta(race, id) {
  if (id === OTHER) return { short: "Diğer", color: "#9e9e9e" };
  return race.meta.get(id) || { short: id, color: "#9e9e9e" };
}

function addOther(poll) {
  const other = Object.entries(poll.results)
    .filter(([id, value]) => !MAIN_PARTIES.includes(id) && typeof value === "number")
    .reduce((sum, [, value]) => sum + value, 0);
  return { ...poll, results: { ...poll.results, [OTHER]: other } };
}

function parliamentActual(data) {
  const shares = data.national.shares;
  const other = Object.entries(shares)
    .filter(([id]) => !MAIN_PARTIES.includes(id))
    .reduce((sum, [, value]) => sum + value, 0);
  const actual = {};
  for (const id of MAIN_PARTIES) actual[id] = shares[id] || 0;
  actual[OTHER] = other;
  return actual;
}

function buildRaces() {
  const president = state.pollData.datasets.president;
  const parliament = state.pollData.datasets.parliament;
  const candidateMeta = new Map(
    state.data.president.candidates.map((candidate) => [candidate.id, candidate])
  );
  const partyMeta = new Map(
    state.data.parties.map((party) => [party.id, party])
  );

  state.races = {
    presidentFirst: {
      key: "presidentFirst",
      label: "Cumhurbaşkanı 1. Tur",
      shortLabel: "CB 1. Tur",
      electionDay: "2023-05-14",
      entities: ["A", "B", "C", "D"],
      actual: state.data.president.first_round.national.shares,
      meta: candidateMeta,
      polls: president.polls.filter((poll) => poll.round === 1),
    },
    presidentRunoff: {
      key: "presidentRunoff",
      label: "Cumhurbaşkanı 2. Tur",
      shortLabel: "CB 2. Tur",
      electionDay: "2023-05-28",
      entities: ["A", "B"],
      actual: state.data.president.runoff.national.shares,
      meta: candidateMeta,
      polls: president.polls.filter((poll) => poll.round === 2),
    },
    parliament: {
      key: "parliament",
      label: "Milletvekili",
      shortLabel: "Milletvekili",
      electionDay: "2023-05-14",
      entities: [...MAIN_PARTIES, OTHER],
      actual: parliamentActual(state.data),
      meta: partyMeta,
      polls: parliament.polls.map(addOther),
    },
  };
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
  buildRaces();
  buildRaceSwitch();
  readUrl();
  attachControls();
  setGeneratedAt();
  applyRace(state.raceKey, { keepCutoff: true });
}

function buildRaceSwitch() {
  const container = $("race-switch");
  container.innerHTML = Object.values(state.races)
    .map(
      (race) =>
        `<button type="button" class="race-button" data-race="${race.key}">${race.label}</button>`
    )
    .join("");
  for (const button of container.querySelectorAll(".race-button")) {
    button.addEventListener("click", () => {
      applyRace(button.dataset.race, { keepCutoff: false });
    });
  }
}

function updateRaceButtons() {
  for (const button of document.querySelectorAll(".race-button")) {
    button.classList.toggle("active", button.dataset.race === state.raceKey);
  }
}

function applyRace(key, { keepCutoff = false } = {}) {
  if (!state.races[key]) return;
  state.raceKey = key;
  const race = currentRace();
  const dates = race.polls.map((poll) => poll.field_end).sort();
  const minDate = dates[0] || race.electionDay;
  $("cutoff").min = minDate;
  $("cutoff").max = race.electionDay;
  if (!keepCutoff || !state.cutoff || state.cutoff < minDate || state.cutoff > race.electionDay) {
    state.cutoff = race.electionDay;
  }
  $("cutoff").value = state.cutoff;
  updateRaceButtons();
  render();
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  const race = params.get("race");
  if (race && state.races[race]) state.raceKey = race;
  const halfLife = Number(params.get("hl"));
  if (Number.isFinite(halfLife)) state.halfLife = Math.min(60, Math.max(7, halfLife));
  if (params.has("cutoff")) state.cutoff = params.get("cutoff");
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
  $("cutoff").addEventListener("change", (event) => {
    state.cutoff = event.target.value;
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
    state.cutoff = currentRace().electionDay;
    $("half-life").value = 28;
    $("half-life-value").textContent = "28 gün";
    $("house-effects").checked = false;
    $("normalize").checked = true;
    $("cutoff").value = state.cutoff;
    render();
  });
}

function render() {
  const race = currentRace();
  const polls = race.polls;
  const entities = race.entities;
  const options = {
    halfLifeDays: state.halfLife,
    normalize: state.normalize,
    houseEffects: state.houseEffects,
    defaultSample: medianSample(polls),
  };
  const aggregate = aggregateAt(polls, entities, state.cutoff, options);
  const uncertainty = bootstrapAggregate(
    polls,
    entities,
    state.cutoff,
    options,
    400
  );
  const dates = polls.map((poll) => poll.field_end).sort();
  const start = dates[0] || state.cutoff;
  const trend = buildTrend(polls, entities, start, state.cutoff, options);

  state.aggregate = aggregate;
  state.trend = trend;
  state.polls = polls;

  drawChart(race, polls, trend, aggregate);
  updateAggregateTable(race, aggregate, uncertainty);
  updatePollsterTable(race, aggregate);
  updatePollTable(race, polls);
  updateMeta(race, aggregate, polls);
  updateUrl();
}

function drawChart(race, polls, trend, aggregate) {
  const d3 = globalThis.d3;
  const svg = d3.select("#trend-chart");
  svg.selectAll("*").remove();
  const legend = $("trend-legend");

  if (!trend.length) {
    svg
      .append("text")
      .attr("x", 450)
      .attr("y", 200)
      .attr("text-anchor", "middle")
      .attr("class", "chart-empty")
      .text("Seçili kesimde anket yok.");
    legend.innerHTML = "";
    return;
  }

  const sorted = [...race.entities].sort(
    (a, b) => (aggregate.shares[b] || 0) - (aggregate.shares[a] || 0)
  );
  const display = race.key === "presidentFirst" || race.key === "presidentRunoff"
    ? sorted
    : sorted.slice(0, 5);

  const width = 900;
  const height = 420;
  const margin = { top: 22, right: 150, bottom: 34, left: 48 };
  const start = toDate(trend[0].date);
  const end = toDate(state.cutoff);
  const domainStart = start.getTime() === end.getTime()
    ? d3.timeDay.offset(start, -1)
    : start;
  const domainEnd = start.getTime() === end.getTime()
    ? d3.timeDay.offset(end, 1)
    : end;
  const x = d3
    .scaleTime()
    .domain([domainStart, domainEnd])
    .range([margin.left, width - margin.right]);

  const maxValue = Math.max(
    ...trend.flatMap((point) =>
      display.map((id) => (point.shares[id] == null ? 0 : point.shares[id]))
    ),
    ...display.map((id) => aggregate.shares[id] || 0)
  );
  const yMax = Math.min(0.9, Math.max(0.45, Math.ceil((maxValue + 0.08) * 10) / 10));
  const y = d3
    .scaleLinear()
    .domain([0, yMax * 100])
    .range([height - margin.bottom, margin.top]);

  const plot = svg.append("g");
  const ticks = d3.range(0, Math.round(yMax * 100) + 1, 10);
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
        .tickFormat((value) => `${value}%`)
    );

  if (yMax >= 0.5) {
    plot
      .append("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(50))
      .attr("y2", y(50))
      .attr("class", "chart-majority");
    plot
      .append("text")
      .attr("x", width - margin.right + 6)
      .attr("y", y(50) + 4)
      .attr("class", "chart-majority-label")
      .text("50%");
  }

  const line = d3
    .line()
    .defined((point) => point.value != null)
    .x((point) => x(toDate(point.date)))
    .y((point) => y(point.value))
    .curve(d3.curveMonotoneX);

  for (const id of display) {
    const meta = entityMeta(race, id);
    const values = trend.map((point) => ({
      date: point.date,
      value: point.shares[id] == null ? null : point.shares[id] * 100,
    }));
    plot
      .append("path")
      .datum(values)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", meta.color)
      .attr("stroke-width", 2.5)
      .attr("stroke-linejoin", "round");
  }

  for (const poll of polls) {
    if (poll.field_end > state.cutoff) continue;
    const shares = normalizePoll(poll, race.entities, state.normalize);
    if (!shares) continue;
    for (const id of display) {
      if (shares[id] == null) continue;
      const meta = entityMeta(race, id);
      plot
        .append("circle")
        .attr("cx", x(toDate(poll.field_end)))
        .attr("cy", y(shares[id] * 100))
        .attr("r", 2.7)
        .attr("fill", meta.color)
        .attr("opacity", 0.32)
        .append("title")
        .text(
          `${poll.pollster} · ${formatDateLong(poll.field_end)} · ${formatPct(
            shares[id] * 100
          )}`
        );
    }
  }

  legend.innerHTML = display
    .map((id) => {
      const meta = entityMeta(race, id);
      return `<span class="legend-item"><i style="background:${meta.color}"></i>${meta.short}</span>`;
    })
    .join("");
}

function updateAggregateTable(race, aggregate, uncertainty) {
  const actual = race.actual || {};
  const rows = [...race.entities]
    .sort((a, b) => (aggregate.shares[b] || 0) - (aggregate.shares[a] || 0))
    .map((id) => {
      const meta = entityMeta(race, id);
      const value = aggregate.shares[id] || 0;
      const actualValue = actual[id];
      const diff = actualValue == null ? null : value - actualValue;
      const diffClass = diff == null ? "" : diff > 0 ? "pos" : diff < 0 ? "neg" : "";
      const interval = uncertainty?.intervals?.[id];
      const ci = interval
        ? `%90 GA ${ciFormat.format(interval.low * 100)}–${ciFormat.format(
            interval.high * 100
          )}`
        : "";
      return `<tr>
        <td><span class="swatch" style="background:${meta.color}"></span>${meta.short}</td>
        <td class="num">${formatPct(value * 100)}${
          ci ? `<div class="ci">${ci}</div>` : ""
        }</td>
        <td class="num muted">${actualValue == null ? "–" : formatPct(actualValue * 100)}</td>
        <td class="num ${diffClass}">${diff == null ? "–" : formatSignedPct(diff)}</td>
      </tr>`;
    })
    .join("");
  $("aggregate-table").innerHTML = rows;
}

function updatePollsterTable(race, aggregate) {
  const container = $("pollster-table");
  if (!state.houseEffects || !aggregate.effects) {
    container.innerHTML =
      `<p class="hint small">Kapalı. Pollster etkisini düzeltmek için kutuyu işaretleyin.</p>`;
    return;
  }
  const entries = Object.entries(aggregate.effects)
    .map(([pollster, data]) => {
      let largest = null;
      for (const [id, effect] of Object.entries(data.effects)) {
        if (largest == null || Math.abs(effect) > Math.abs(largest.effect)) {
          largest = { id, effect };
        }
      }
      return { pollster, n: data.n, largest };
    })
    .sort((a, b) => b.n - a.n)
    .slice(0, 12);

  const rows = entries
    .map((entry) => {
      const meta = entry.largest ? entityMeta(race, entry.largest.id) : null;
      const diff = entry.largest ? entry.largest.effect : 0;
      const className = diff > 0 ? "pos" : diff < 0 ? "neg" : "";
      return `<div class="effect-row">
        <span>${escapeHtml(entry.pollster)}</span>
        <span>${entry.n}</span>
        <span class="${className}">${meta ? `${meta.short} ${formatSignedPct(diff)}` : "–"}</span>
      </div>`;
    })
    .join("");
  container.innerHTML = `<div class="effect-head"><span>Pollster</span><span>Anket</span><span>En büyük</span></div>${rows}`;
}

function updatePollTable(race, polls) {
  const head = $("poll-table-head");
  head.innerHTML = `<tr>
    <th>Tarih</th>
    <th>Anket</th>
    <th>Örneklem</th>
    ${race.entities.map((id) => `<th>${entityMeta(race, id).short}</th>`).join("")}
  </tr>`;

  const rows = [...polls]
    .sort((a, b) => (a.field_end < b.field_end ? 1 : a.field_end > b.field_end ? -1 : 0))
    .map((poll) => {
      const shares = normalizePoll(poll, race.entities, state.normalize);
      if (!shares) return "";
      const cells = race.entities
        .map((id) =>
          shares[id] == null
            ? `<td class="num">–</td>`
            : `<td class="num">${formatPct(shares[id] * 100)}</td>`
        )
        .join("");
      return `<tr>
        <td title="${escapeHtml(poll.source_date_text || "")}">${formatDateShort(
          poll.field_end
        )}</td>
        <td>${escapeHtml(poll.pollster)}</td>
        <td class="num">${poll.sample_size == null ? "–" : formatInt(poll.sample_size)}</td>
        ${cells}
      </tr>`;
    })
    .join("");
  $("poll-table-body").innerHTML = rows;
}

function updateMeta(race, aggregate, polls) {
  const pollsters = new Set(polls.map((poll) => poll.pollster));
  $("aggregate-summary").textContent = `${aggregate.nPolls} anket · son anket ${
    aggregate.lastPoll ? formatDateLong(aggregate.lastPoll) : "–"
  } · ${pollsters.size} pollster`;
  $("chart-subtitle").textContent = `${race.label} · ${
    state.houseEffects ? "pollster düzeltmeli" : "ham"
  } ortalama`;
  $("poll-count").textContent = `${polls.length} anket`;
  $("poll-list-meta").textContent = `${polls.length} anket · kesim ${formatDateLong(
    state.cutoff
  )}`;
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("race", state.raceKey);
  params.set("hl", String(state.halfLife));
  params.set("cutoff", state.cutoff);
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
