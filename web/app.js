import { allocateDistricts } from "./modules/allocate.js";
import { createHemicycle } from "./modules/hemicycle.js";
import { createMap } from "./modules/map.js";
import {
  clamp,
  formatInt,
  formatPct,
  formatSigned,
  normalizeName,
} from "./modules/format.js";
import {
  MAIN_PARTIES,
  parliamentAggregate,
} from "./modules/poll_preset.js";
import { PARTY_OUTCOME, swingFactor, tiltFor } from "./modules/projection.js";

const MAIN_ORDER = [...MAIN_PARTIES];
const OTHER_COLOR = "#9e9e9e";

const state = {
  data: null,
  geojson: null,
  ilceGeo: null,
  pollData: null,
  pollDataByYear: {},
  elections: {},
  year: "2023",
  election: null,
  demographicSwing: null,
  seatProjection: null,
  swingStrength: 0.6,
  partiesById: new Map(),
  mainParties: [],
  geoDisplay: new Map(),
  ilceDisplay: new Map(),
  shares: {},
  threshold: 0.07,
  useAlliances: true,
  selectedKey: null,
  mapMode: "province",
  provinces: new Map(),
  ilce: new Map(),
  result: null,
  map: null,
  ilceMapView: null,
  hemicycle: null,
};

function $(id) {
  return document.getElementById(id);
}

async function main() {
  const [data, geojson, ilceGeo, polls2023, polls2028, elections, demographicSwing, seatProjection] = await Promise.all([
    fetch("./data/parliament_2023.json").then((response) => {
      if (!response.ok) throw new Error(`data ${response.status}`);
      return response.json();
    }),
    fetch("./geo/tr-provinces.geojson").then((response) => {
      if (!response.ok) throw new Error(`province geo ${response.status}`);
      return response.json();
    }),
    fetch("./geo/tr-ilce.geojson").then((response) => {
      if (!response.ok) throw new Error(`ilce geo ${response.status}`);
      return response.json();
    }),
    fetch("./data/polls_2023.json").then((response) => {
      if (!response.ok) throw new Error(`polls ${response.status}`);
      return response.json();
    }),
    fetch("./data/polls_2028.json").then((response) => {
      if (!response.ok) throw new Error(`polls 2028 ${response.status}`);
      return response.json();
    }),
    fetch("./data/elections.json").then((response) => {
      if (!response.ok) throw new Error(`elections ${response.status}`);
      return response.json();
    }),
    fetch("./data/demographic_swing.json").then((response) => {
      if (!response.ok) throw new Error(`swing ${response.status}`);
      return response.json();
    }),
    fetch("./data/seat_projection_2028.json").then((response) => {
      if (!response.ok) throw new Error(`seat projection ${response.status}`);
      return response.json();
    }),
  ]);

  state.data = data;
  state.geojson = geojson;
  state.pollDataByYear = { "2023": polls2023, "2028": polls2028 };
  state.elections = elections;
  state.demographicSwing = demographicSwing;
  state.seatProjection = seatProjection;
  state.partiesById = new Map(data.parties.map((party) => [party.id, party]));
  state.mainParties = MAIN_ORDER.map((id) => state.partiesById.get(id)).filter(Boolean);
  state.geoDisplay = new Map(
    geojson.features.map((feature) => [
      normalizeName(feature.properties.shapeName),
      feature.properties.shapeName,
    ])
  );
  state.ilceDisplay = new Map(
    ilceGeo.features.map((feature) => [
      feature.properties.shapeID,
      {
        name: feature.properties.shapeName,
        province: feature.properties.province,
      },
    ])
  );
  state.threshold = data.meta.threshold;
  state.useAlliances = true;

  for (const party of state.mainParties) {
    state.shares[party.id] =
      ((data.national.votes[party.id] || 0) / data.national.valid_votes) * 100;
  }

  readUrl();
  state.election = state.elections[state.year] || state.elections["2023"];
  state.pollData = state.pollDataByYear[state.year] || state.pollDataByYear["2023"];
  buildElectionControl();
  buildControls();
  normalizeShares();
  syncControls();
  buildLegend();
  setGeneratedAt();

  state.map = createMap($("map"), geojson, data.parties, {
    onHover: handleProvinceHover,
    onSelect: handleProvinceSelect,
  });
  state.ilceMapView = createMap($("ilce-map"), ilceGeo, data.parties, {
    keyFn: (feature) => feature.properties.shapeID,
    onHover: handleIlceHover,
    onSelect: handleIlceSelect,
  });
  state.hemicycle = createHemicycle($("hemicycle"), 600);

  $("reset").addEventListener("click", resetTo2023);
  $("apply-polls").addEventListener("click", applyPollAverage);
  $("copy-link").addEventListener("click", copyLink);
  $("map-province").addEventListener("click", () => setMapMode("province"));
  $("map-ilce").addEventListener("click", () => setMapMode("ilce"));
  $("threshold").addEventListener("input", (event) => {
    const value = Number(event.target.value);
    if (Number.isFinite(value)) state.threshold = clamp(value, 0, 15) / 100;
    render();
  });
  $("alliances").addEventListener("change", (event) => {
    state.useAlliances = event.target.checked;
    render();
  });
  $("demographic-swing").addEventListener("change", (event) => {
    state.swingStrength = event.target.checked ? Number($("swing-strength").value) / 100 : 0;
    $("swing-strength").disabled = !event.target.checked;
    render();
  });
  $("swing-strength").addEventListener("input", (event) => {
    state.swingStrength = $("demographic-swing").checked ? Number(event.target.value) / 100 : 0;
    $("swing-strength-value").textContent = `${event.target.value}%`;
    render();
  });

  setMapMode(state.mapMode);
  render();
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  for (const party of state.mainParties) {
    const key = party.id.toLowerCase();
    if (params.has(key)) {
      const value = Number(params.get(key));
      if (Number.isFinite(value)) state.shares[party.id] = clamp(value, 0, 100);
    }
  }
  if (params.has("t")) {
    const value = Number(params.get("t"));
    if (Number.isFinite(value)) state.threshold = clamp(value, 0, 15) / 100;
  }
  if (params.has("a")) state.useAlliances = params.get("a") !== "0";
  const year = params.get("year");
  if (year && state.elections[year]) state.year = year;
  if (params.has("ds")) {
    const value = Number(params.get("ds"));
    if (Number.isFinite(value)) state.swingStrength = clamp(value, 0, 100) / 100;
  }
  const mode = params.get("m");
  if (mode === "province" || mode === "ilce") state.mapMode = mode;
}

function buildElectionControl() {
  const select = $("election-year");
  select.innerHTML = Object.keys(state.elections)
    .sort()
    .map((year) => `<option value="${year}">${
      year === "2023" ? "2023 sonucu" : `${year} projeksiyonu`
    }</option>`)
    .join("");
  select.value = state.year;
  select.addEventListener("change", () => {
    state.year = select.value;
    state.election = state.elections[state.year] || state.elections["2023"];
    state.pollData = state.pollDataByYear[state.year] || state.pollDataByYear["2023"];
    updateElectionNote();
    render();
  });
  updateElectionNote();
}

function updateElectionNote() {
  const election = state.election || state.elections["2023"];
  const datasets = state.pollData?.datasets || {};
  const hasPolls =
    (datasets.president?.polls?.length || 0) + (datasets.parliament?.polls?.length || 0) > 0;
  $("election-note").textContent =
    election.status === "projection"
      ? `${election.year} projeksiyonu: 2023 tabanı ve 2028 sandalye projeksiyonu; henüz anket verisi yok.`
      : "2023 resmi sonucu ve anket ortalaması.";
  $("apply-polls").disabled = !hasPolls;
  $("apply-polls").textContent = hasPolls ? "Anket ortalaması" : "Anket verisi yok";
}

function buildControls() {
  const container = $("party-controls");
  container.innerHTML = state.mainParties
    .map(
      (party) => `
        <div class="party-row" data-party="${party.id}">
          <span class="swatch" style="background:${party.color}"></span>
          <label for="range-${party.id}">${party.short}</label>
          <input id="range-${party.id}" class="share-range" type="range"
                 min="0" max="100" step="0.1" value="${state.shares[party.id].toFixed(1)}"
                 style="accent-color:${party.color}">
          <input id="num-${party.id}" class="share-number" type="number"
                 min="0" max="100" step="0.1" value="${state.shares[party.id].toFixed(1)}">
          <span class="pct">%</span>
        </div>`
    )
    .join("");

  for (const party of state.mainParties) {
    const range = $(`range-${party.id}`);
    const number = $(`num-${party.id}`);
    range.addEventListener("input", () => setShare(party.id, Number(range.value)));
    number.addEventListener("input", () => setShare(party.id, Number(number.value)));
  }

  $("threshold").value = (state.threshold * 100).toFixed(1);
  $("alliances").checked = state.useAlliances;
  $("demographic-swing").checked = state.swingStrength > 0;
  $("swing-strength").value = Math.round(state.swingStrength * 100);
  $("swing-strength").disabled = state.swingStrength <= 0;
  $("swing-strength-value").textContent = `${Math.round(state.swingStrength * 100)}%`;
}

function buildLegend() {
  const legendParties = [...state.mainParties];
  const bbp = state.partiesById.get("P8");
  if (bbp) legendParties.push(bbp);
  const items = legendParties
    .map(
      (party) =>
        `<span class="legend-item"><i style="background:${party.color}"></i>${party.short}</span>`
    )
    .join("");
  $("map-legend").innerHTML =
    items +
    `<span class="legend-item"><i style="background:${OTHER_COLOR}"></i>Diğer</span>`;
}

function setGeneratedAt() {
  const value = state.data.meta.generated_at;
  if (!value) return;
  const formatted = new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
  $("generated-at").textContent = `Veri: ${formatted}`;
}

function normalizeShares() {
  const sum = MAIN_ORDER.reduce((total, id) => total + (state.shares[id] || 0), 0);
  if (sum > 100 && sum > 0) {
    const scale = 100 / sum;
    for (const id of MAIN_ORDER) state.shares[id] = (state.shares[id] || 0) * scale;
  }
}

function syncControls() {
  for (const party of state.mainParties) {
    const value = state.shares[party.id].toFixed(1);
    const range = $(`range-${party.id}`);
    const number = $(`num-${party.id}`);
    if (range) range.value = value;
    if (number) number.value = value;
  }
  updateOtherShare();
}

function setShare(id, value) {
  if (!Number.isFinite(value)) return;
  state.shares[id] = clamp(value, 0, 100);
  normalizeShares();
  syncControls();
  render();
}

function updateOtherShare() {
  const sum = MAIN_ORDER.reduce((total, id) => total + (state.shares[id] || 0), 0);
  $("other-share").textContent = formatPct(Math.max(0, 100 - sum));
}

function effectiveFactor(id, factor, provinceKey) {
  return swingFactor(
    factor,
    tiltFor(state.demographicSwing, provinceKey, PARTY_OUTCOME[id]),
    state.swingStrength
  );
}

function buildScenarioDistricts() {
  const { data } = state;
  const totalValid = data.national.valid_votes;
  const base = data.national.votes;
  const mainIds = new Set(MAIN_ORDER);
  const sumMain = MAIN_ORDER.reduce((total, id) => total + state.shares[id], 0);
  const otherShare = Math.max(0, 100 - sumMain);
  const baseMain = MAIN_ORDER.reduce((total, id) => total + (base[id] || 0), 0);
  const baseOther = totalValid - baseMain;

  const factors = {};
  for (const [id, votes] of Object.entries(base)) {
    if (mainIds.has(id)) {
      const target = (state.shares[id] / 100) * totalValid;
      factors[id] = votes > 0 ? target / votes : 0;
    } else {
      const target = (otherShare / 100) * totalValid;
      factors[id] = baseOther > 0 ? target / baseOther : 0;
    }
  }

  const scaled = data.districts.map((district) => {
    const votes = {};
    const provinceKey = normalizeName(district.province_base);
    for (const [id, value] of Object.entries(district.votes)) {
      const factor = effectiveFactor(id, factors[id] || 0, provinceKey);
      if (factor > 0) votes[id] = value * factor;
    }
    const projectedSeats =
      state.year === "2028"
        ? state.seatProjection?.districts?.[district.id]
        : null;
    return {
      ...district,
      seats: projectedSeats ?? district.seats,
      votes,
    };
  });

  const total = scaled.reduce(
    (sum, district) =>
      sum + Object.values(district.votes).reduce((a, b) => a + b, 0),
    0
  );
  if (total > 0) {
    const norm = totalValid / total;
    for (const district of scaled) {
      for (const id of Object.keys(district.votes)) district.votes[id] *= norm;
    }
  }
  return { districts: scaled, factors };
}

function aggregateProvinces(districts, result) {
  const provinces = new Map();
  for (const district of districts) {
    const key = normalizeName(district.province_base);
    let province = provinces.get(key);
    if (!province) {
      province = {
        name: district.province_base,
        geo_key: key,
        seats: 0,
        valid_votes: 0,
        ballots_cast: 0,
        electorate: 0,
        votes: {},
        scenario_seats: {},
      };
      provinces.set(key, province);
    }
    province.seats += district.seats;
    province.valid_votes += district.valid_votes;
    province.ballots_cast += district.ballots_cast;
    province.electorate += district.electorate;
    for (const [id, value] of Object.entries(district.votes)) {
      province.votes[id] = (province.votes[id] || 0) + value;
    }
  }

  for (const province of provinces.values()) {
    const total = Object.values(province.votes).reduce((a, b) => a + b, 0);
    province.shares = {};
    for (const [id, value] of Object.entries(province.votes)) {
      province.shares[id] = total ? value / total : 0;
    }
    const sorted = Object.entries(province.votes).sort((a, b) => b[1] - a[1]);
    province.winner = sorted[0]?.[0] || null;
    province.scenario_seats = result.seatsByProvince[province.name] || {};
    province.turnout = province.electorate
      ? province.ballots_cast / province.electorate
      : 0;
  }
  return provinces;
}

function aggregateIlce(factors) {
  const ilce = new Map();
  for (const base of state.data.ilce) {
    const votes = {};
    const provinceKey = base.province_key || normalizeName(base.province_base);
    for (const [id, value] of Object.entries(base.votes)) {
      const factor = effectiveFactor(id, factors[id] || 0, provinceKey);
      if (factor > 0) votes[id] = value * factor;
    }
    const total = Object.values(votes).reduce((a, b) => a + b, 0);
    const shares = {};
    for (const [id, value] of Object.entries(votes)) {
      shares[id] = total ? value / total : 0;
    }
    const sorted = Object.entries(votes).sort((a, b) => b[1] - a[1]);
    ilce.set(base.geo_id, {
      ...base,
      votes,
      shares,
      winner: sorted[0]?.[0] || null,
    });
  }
  return ilce;
}

function render() {
  const { districts, factors } = buildScenarioDistricts();
  const alliances = state.useAlliances ? state.data.meta.alliances : {};
  const result = allocateDistricts(districts, alliances, state.threshold);
  const provinces = aggregateProvinces(districts, result);
  const ilce = aggregateIlce(factors);

  state.result = result;
  state.provinces = provinces;
  state.ilce = ilce;

  state.hemicycle.update(result.seatsByParty, state.data.parties);
  state.map.update(provinces);
  state.ilceMapView.update(ilce);
  state.map.setSelected(state.mapMode === "province" ? state.selectedKey : null);
  state.ilceMapView.setSelected(state.mapMode === "ilce" ? state.selectedKey : null);
  updateTable(result);
  updateSummary(result);
  updateOtherShare();
  updateUrl();
  if (state.selectedKey) {
    if (state.mapMode === "province") showProvinceDetail(state.selectedKey);
    else showIlceDetail(state.selectedKey);
  }
}

function updateTable(result) {
  const national = result.national;
  const total = Object.values(national).reduce((a, b) => a + b, 0);
  const rows = [];
  let mainSeats = 0;
  let mainShare = 0;
  let mainActual = 0;

  for (const id of MAIN_ORDER) {
    const party = state.partiesById.get(id);
    if (!party) continue;
    const seats = result.seatsByParty[id] || 0;
    const share = total ? (national[id] || 0) / total : 0;
    const actual = party.actual_seats || 0;
    mainSeats += seats;
    mainShare += share;
    mainActual += actual;
    rows.push(rowHtml(party, share, seats, actual, seats - actual));
  }

  const otherSeats = 600 - mainSeats;
  const otherActual = 600 - mainActual;
  rows.push(
    rowHtml(
      { id: "other", short: "Diğer", color: OTHER_COLOR },
      Math.max(0, 1 - mainShare),
      otherSeats,
      otherActual,
      otherSeats - otherActual
    )
  );

  $("party-table").innerHTML = rows.join("");
}

function rowHtml(party, share, seats, actual, diff) {
  const diffClass = diff > 0 ? "pos" : diff < 0 ? "neg" : "";
  return `<tr>
    <td><span class="swatch" style="background:${party.color}"></span>${party.short}</td>
    <td class="num">${formatPct(share * 100)}</td>
    <td class="num">${formatInt(seats)}</td>
    <td class="num muted">${formatInt(actual)}</td>
    <td class="num ${diffClass}">${formatSigned(diff)}</td>
  </tr>`;
}

function updateSummary(result) {
  const entries = Object.entries(result.seatsByParty)
    .filter(([, seats]) => seats > 0)
    .sort((a, b) => b[1] - a[1]);
  const summary = $("summary");
  if (entries.length === 0) {
    summary.textContent = "Sandalye dağıtılamadı";
    return;
  }
  const [id, seats] = entries[0];
  const party = state.partiesById.get(id);
  const name = party?.short || (id.startsWith("I") ? "Bağımsız" : id);
  const color = party?.color || OTHER_COLOR;
  const status = seats >= 301 ? "tek başına çoğunluk" : "çoğunluk yok";
  summary.innerHTML = `<span class="dot" style="background:${color}"></span>En büyük: <strong>${name}</strong> · ${formatInt(
    seats
  )} sandalye · ${status}`;
}

function updateUrl() {
  const params = new URLSearchParams();
  for (const id of MAIN_ORDER) params.set(id.toLowerCase(), state.shares[id].toFixed(1));
  params.set("t", (state.threshold * 100).toFixed(1));
  params.set("a", state.useAlliances ? "1" : "0");
  params.set("m", state.mapMode);
  params.set("year", state.year);
  params.set("ds", String(Math.round(state.swingStrength * 100)));
  try {
    history.replaceState(null, "", `?${params.toString()}`);
  } catch {
    // file:// or a restricted context; the app still works without URL state.
  }
}

function showTooltip({ title, subtitle, leaders, meta }, event) {
  const tooltip = $("tooltip");
  const rows = leaders
    .map(({ id, share }) => {
      const party = state.partiesById.get(id);
      const name = party?.short || (id.startsWith("I") ? "Bağımsız" : id);
      const color = party?.color || OTHER_COLOR;
      return `<div class="tip-row"><span class="dot" style="background:${color}"></span>${name}<span>${formatPct(
        share * 100
      )}</span></div>`;
    })
    .join("");

  tooltip.innerHTML = `<div class="tip-title">${title}</div>${
    subtitle ? `<div class="tip-sub">${subtitle}</div>` : ""
  }${rows}<div class="tip-meta">${meta}</div>`;
  tooltip.hidden = false;

  const pad = 14;
  const rect = tooltip.getBoundingClientRect();
  const x = event?.clientX ?? 24;
  const y = event?.clientY ?? 24;
  let left = x + pad;
  let top = y + pad;
  if (left + rect.width > window.innerWidth - 8) left = x - rect.width - pad;
  if (top + rect.height > window.innerHeight - 8) top = y - rect.height - pad;
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${Math.max(8, top)}px`;
}

function hideTooltip() {
  $("tooltip").hidden = true;
}

function handleProvinceHover(feature, event) {
  if (!feature) {
    hideTooltip();
    return;
  }
  const key = normalizeName(feature.properties.shapeName);
  const province = state.provinces.get(key);
  if (!province) {
    hideTooltip();
    return;
  }
  const total = Object.values(province.votes).reduce((a, b) => a + b, 0);
  const leaders = Object.entries(province.votes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([id, value]) => ({ id, share: total ? value / total : 0 }));
  showTooltip(
    {
      title: feature.properties.shapeName,
      leaders,
      meta: `${formatInt(province.seats)} sandalye · ${formatPct(
        province.turnout * 100
      )} katılım`,
    },
    event
  );
}

function handleIlceHover(feature, event) {
  if (!feature) {
    hideTooltip();
    return;
  }
  const row = state.ilce.get(feature.properties.shapeID);
  if (!row) {
    hideTooltip();
    return;
  }
  const total = Object.values(row.votes).reduce((a, b) => a + b, 0);
  const leaders = Object.entries(row.votes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([id, value]) => ({ id, share: total ? value / total : 0 }));
  showTooltip(
    {
      title: feature.properties.shapeName,
      subtitle: feature.properties.province,
      leaders,
      meta: `${formatInt(row.valid_votes)} geçerli oy`,
    },
    event
  );
}

function handleProvinceSelect(feature) {
  if (!feature || state.mapMode !== "province") return;
  const key = normalizeName(feature.properties.shapeName);
  state.selectedKey = state.selectedKey === key ? null : key;
  state.map.setSelected(state.selectedKey);
  state.ilceMapView.setSelected(null);
  if (state.selectedKey) showProvinceDetail(state.selectedKey);
  else $("province-detail").innerHTML = "";
}

function handleIlceSelect(feature) {
  if (!feature || state.mapMode !== "ilce") return;
  const key = feature.properties.shapeID;
  state.selectedKey = state.selectedKey === key ? null : key;
  state.ilceMapView.setSelected(state.selectedKey);
  state.map.setSelected(null);
  if (state.selectedKey) showIlceDetail(state.selectedKey);
  else $("province-detail").innerHTML = "";
}

function setMapMode(mode) {
  state.mapMode = mode;
  state.selectedKey = null;
  if (state.map) state.map.setSelected(null);
  if (state.ilceMapView) state.ilceMapView.setSelected(null);
  $("map").classList.toggle("hidden", mode !== "province");
  $("ilce-map").classList.toggle("hidden", mode !== "ilce");
  $("map-province").classList.toggle("active", mode === "province");
  $("map-ilce").classList.toggle("active", mode === "ilce");
  $("province-detail").innerHTML = "";
  hideTooltip();
  updateUrl();
}

function showProvinceDetail(key) {
  const province = state.provinces.get(key);
  const detail = $("province-detail");
  if (!province) {
    detail.innerHTML = "";
    return;
  }
  const total = Object.values(province.votes).reduce((a, b) => a + b, 0);
  const entries = Object.entries(province.votes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const rows = entries
    .map(([id, value]) => {
      const party = state.partiesById.get(id);
      const name = party?.short || (id.startsWith("I") ? "Bağımsız" : id);
      const color = party?.color || OTHER_COLOR;
      return `<div class="detail-row">
        <span class="dot" style="background:${color}"></span>
        <span>${name}</span>
        <span>${formatPct((value / total) * 100)}</span>
        <span>${formatInt(province.scenario_seats?.[id] || 0)}</span>
      </div>`;
    })
    .join("");

  const name = state.geoDisplay.get(key) || province.name;
  detail.innerHTML = `<div class="detail-head">
      <strong>${name}</strong>
      <span>${formatInt(province.seats)} sandalye · ${formatPct(
    province.turnout * 100
  )} katılım</span>
    </div>
    <div class="detail-labels"><span>Parti</span><span>Oy</span><span>Sand.</span></div>
    ${rows}`;
}

function showIlceDetail(geoId) {
  const row = state.ilce.get(geoId);
  const detail = $("province-detail");
  if (!row) {
    detail.innerHTML = "";
    return;
  }
  const total = Object.values(row.votes).reduce((a, b) => a + b, 0);
  const entries = Object.entries(row.votes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const rows = entries
    .map(([id, value]) => {
      const party = state.partiesById.get(id);
      const name = party?.short || (id.startsWith("I") ? "Bağımsız" : id);
      const color = party?.color || OTHER_COLOR;
      return `<div class="detail-row no-seats">
        <span class="dot" style="background:${color}"></span>
        <span>${name}</span>
        <span>${formatPct((value / total) * 100)}</span>
      </div>`;
    })
    .join("");

  const display = state.ilceDisplay.get(geoId);
  const name = display?.name || row.name;
  const province = display?.province || row.province;
  detail.innerHTML = `<div class="detail-head">
      <strong>${name}</strong>
      <span>${province} · ${formatInt(row.valid_votes)} geçerli oy</span>
    </div>
    ${rows}`;
}

function applyPollAverage() {
  const shares = parliamentAggregate(state.pollData, state.election?.date || "2023-05-14");
  if (!Object.keys(shares).length) {
    updateElectionNote();
    return;
  }
  for (const id of MAIN_ORDER) {
    state.shares[id] = (shares[id] || 0) * 100;
  }
  normalizeShares();
  syncControls();
  state.selectedKey = null;
  state.map.setSelected(null);
  state.ilceMapView.setSelected(null);
  $("province-detail").innerHTML = "";
  hideTooltip();
  render();
}

function resetTo2023() {
  for (const party of state.mainParties) {
    state.shares[party.id] =
      ((state.data.national.votes[party.id] || 0) /
        state.data.national.valid_votes) *
      100;
  }
  state.threshold = state.data.meta.threshold;
  state.useAlliances = true;
  state.selectedKey = null;
  $("threshold").value = (state.threshold * 100).toFixed(1);
  $("alliances").checked = true;
  state.map.setSelected(null);
  state.ilceMapView.setSelected(null);
  $("province-detail").innerHTML = "";
  hideTooltip();
  syncControls();
  render();
}

async function copyLink() {
  const button = $("copy-link");
  try {
    await navigator.clipboard.writeText(location.href);
    button.textContent = "Kopyalandı";
  } catch {
    window.prompt("Bağlantı:", location.href);
  }
  setTimeout(() => {
    button.textContent = "Bağlantıyı kopyala";
  }, 1500);
}

main().catch((error) => {
  console.error(error);
  const panel = document.querySelector(".map-panel");
  if (panel) {
    panel.innerHTML = `<div class="error">Veri yüklenemedi: ${error.message}</div>`;
  }
});
