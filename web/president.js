import { createMap } from "./modules/map.js";
import {
  clamp,
  formatInt,
  formatPct,
  normalizeName,
} from "./modules/format.js";
import { presidentAggregate } from "./modules/poll_preset.js";

const CANDIDATE_ORDER = ["A", "B", "C", "D"];

const state = {
  data: null,
  geojson: null,
  pollData: null,
  candidates: [],
  byId: new Map(),
  names: {},
  shares: {},
  transfers: {},
  defaultTransfer: 0.5,
  mapRound: "first",
  selectedKey: null,
  transferKey: null,
  first: null,
  runoff: null,
  currentProvinces: new Map(),
  geoDisplay: new Map(),
  map: null,
};

function $(id) {
  return document.getElementById(id);
}

function candidateName(id) {
  return state.names[id] || state.byId.get(id)?.short || id;
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

async function main() {
  const [data, geojson, pollData] = await Promise.all([
    fetch("./data/parliament_2023.json").then((response) => {
      if (!response.ok) throw new Error(`data ${response.status}`);
      return response.json();
    }),
    fetch("./geo/tr-provinces.geojson").then((response) => {
      if (!response.ok) throw new Error(`geo ${response.status}`);
      return response.json();
    }),
    fetch("./data/polls_2023.json").then((response) => {
      if (!response.ok) throw new Error(`polls ${response.status}`);
      return response.json();
    }),
  ]);

  state.data = data;
  state.geojson = geojson;
  state.pollData = pollData;
  state.candidates = data.president.candidates;
  state.byId = new Map(state.candidates.map((candidate) => [candidate.id, candidate]));
  state.names = Object.fromEntries(
    state.candidates.map((candidate) => [candidate.id, candidate.short])
  );
  state.shares = Object.fromEntries(
    state.candidates.map((candidate) => [
      candidate.id,
      (data.president.first_round.national.shares[candidate.id] || 0) * 100,
    ])
  );
  state.defaultTransfer = data.president.transfer_default ?? 0.5;
  state.transfers = Object.fromEntries(
    state.candidates.map((candidate) => [
      candidate.id,
      state.defaultTransfer * 100,
    ])
  );
  state.geoDisplay = new Map(
    geojson.features.map((feature) => [
      normalizeName(feature.properties.shapeName),
      feature.properties.shapeName,
    ])
  );

  readUrl();
  normalizeShares();
  buildCandidateControls();
  syncCandidateControls();
  buildLegend();
  setGeneratedAt();

  state.map = createMap($("president-map"), geojson, state.candidates, {
    onHover: handleHover,
    onSelect: handleSelect,
  });

  $("reset").addEventListener("click", resetTo2023);
  $("apply-polls").addEventListener("click", applyPollAverage);
  $("copy-link").addEventListener("click", copyLink);
  $("round-first").addEventListener("click", () => setRound("first"));
  $("round-runoff").addEventListener("click", () => setRound("runoff"));

  setRound(state.mapRound);
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  for (const candidate of state.candidates) {
    const id = candidate.id;
    const share = params.get(id.toLowerCase());
    if (share !== null && Number.isFinite(Number(share))) {
      state.shares[id] = clamp(Number(share), 0, 100);
    }
    const name = params.get(`n${id}`);
    if (name) state.names[id] = name;
    const transfer = params.get(`t${id}`);
    if (transfer !== null && Number.isFinite(Number(transfer))) {
      state.transfers[id] = clamp(Number(transfer), 0, 100);
    }
  }
  const round = params.get("m");
  if (round === "first" || round === "runoff") state.mapRound = round;
}

function buildCandidateControls() {
  const container = $("candidate-controls");
  container.innerHTML = state.candidates
    .map(
      (candidate) => `
        <div class="candidate-row" data-id="${candidate.id}">
          <span class="swatch" style="background:${candidate.color}"></span>
          <input id="name-${candidate.id}" class="candidate-name" type="text"
                 value="${escapeHtml(state.names[candidate.id])}" aria-label="Aday adı">
          <input id="range-${candidate.id}" class="share-range" type="range"
                 min="0" max="100" step="0.1" value="${state.shares[candidate.id].toFixed(1)}"
                 style="accent-color:${candidate.color}">
          <input id="num-${candidate.id}" class="share-number" type="number"
                 min="0" max="100" step="0.1" value="${state.shares[candidate.id].toFixed(1)}">
          <span class="pct">%</span>
        </div>`
    )
    .join("");

  for (const candidate of state.candidates) {
    const id = candidate.id;
    const range = $(`range-${id}`);
    const number = $(`num-${id}`);
    const name = $(`name-${id}`);
    range.addEventListener("input", () => setShare(id, Number(range.value)));
    number.addEventListener("input", () => setShare(id, Number(number.value)));
    name.addEventListener("input", () => {
      state.names[id] = name.value.trim() || candidate.short;
      buildTransferControls();
      render();
    });
  }
}

function syncCandidateControls() {
  for (const candidate of state.candidates) {
    const id = candidate.id;
    const value = state.shares[id].toFixed(1);
    const range = $(`range-${id}`);
    const number = $(`num-${id}`);
    const name = $(`name-${id}`);
    if (range) range.value = value;
    if (number) number.value = value;
    if (name) name.value = state.names[id];
  }
}

function normalizeShares() {
  let total = CANDIDATE_ORDER.reduce((sum, id) => sum + (state.shares[id] || 0), 0);
  if (total <= 0) {
    for (const id of CANDIDATE_ORDER) state.shares[id] = 25;
    total = 100;
  }
  const scale = 100 / total;
  for (const id of CANDIDATE_ORDER) state.shares[id] = (state.shares[id] || 0) * scale;
}

function setShare(id, value) {
  if (!Number.isFinite(value)) return;
  state.shares[id] = clamp(value, 0, 100);
  normalizeShares();
  syncCandidateControls();
  render();
}

function rankCandidates() {
  const ranked = [...state.candidates].sort(
    (a, b) => (state.shares[b.id] || 0) - (state.shares[a.id] || 0)
  );
  return {
    topTwo: ranked.slice(0, 2),
    eliminated: ranked.slice(2),
    ranked,
  };
}

function buildTransferControls() {
  const container = $("transfer-controls");
  const { topTwo, eliminated } = rankCandidates();
  const active = eliminated.filter((candidate) => (state.shares[candidate.id] || 0) > 0);
  if (topTwo.length < 2 || active.length === 0) {
    container.innerHTML = `<p class="hint small">Transfer edilecek aday yok.</p>`;
    return;
  }

  container.innerHTML = active
    .map((candidate) => {
      const value = (
        state.transfers[candidate.id] ?? state.defaultTransfer * 100
      ).toFixed(1);
      return `<div class="transfer-row" data-id="${candidate.id}">
        <div class="transfer-head">
          <span class="transfer-label">${escapeHtml(
            candidateName(candidate.id)
          )} → ${escapeHtml(candidateName(topTwo[0].id))}<small>kalanı ${escapeHtml(
            candidateName(topTwo[1].id)
          )}</small></span>
          <span class="transfer-value">
            <input id="transfer-num-${candidate.id}" class="share-number" type="number"
                   min="0" max="100" step="0.1" value="${value}"> %
          </span>
        </div>
        <input id="transfer-${candidate.id}" class="transfer-range" type="range"
               min="0" max="100" step="0.1" value="${value}"
               style="accent-color:${candidate.color}">
      </div>`;
    })
    .join("");

  for (const candidate of active) {
    const id = candidate.id;
    const range = $(`transfer-${id}`);
    const number = $(`transfer-num-${id}`);
    const update = (value) => {
      if (!Number.isFinite(value)) return;
      state.transfers[id] = clamp(value, 0, 100);
      range.value = state.transfers[id].toFixed(1);
      number.value = state.transfers[id].toFixed(1);
      render();
    };
    range.addEventListener("input", () => update(Number(range.value)));
    number.addEventListener("input", () => update(Number(number.value)));
  }
}

function buildFirstRound() {
  const baseNational = state.data.president.first_round.national.shares;
  const target = {};
  for (const candidate of state.candidates) {
    target[candidate.id] = (state.shares[candidate.id] || 0) / 100;
  }
  const totalTarget = Object.values(target).reduce((a, b) => a + b, 0);
  if (totalTarget > 0) {
    for (const id of Object.keys(target)) target[id] /= totalTarget;
  }

  const provinces = state.data.president.first_round.provinces.map((province) => {
    const raw = {};
    for (const candidate of state.candidates) {
      const id = candidate.id;
      raw[id] = Math.max(
        0,
        (province.shares[id] || 0) + (target[id] || 0) - (baseNational[id] || 0)
      );
    }
    const total = Object.values(raw).reduce((a, b) => a + b, 0);
    const shares = {};
    for (const id of Object.keys(raw)) shares[id] = total ? raw[id] / total : 0;
    const ranked = Object.entries(shares).sort((a, b) => b[1] - a[1]);
    return {
      ...province,
      shares,
      winner: ranked[0]?.[0] || null,
    };
  });

  return { national: target, provinces };
}

function buildRunoff(firstRound) {
  const { topTwo, eliminated } = rankCandidates();
  if (topTwo.length < 2) {
    return { topTwo, eliminated: [], national: {}, provinces: [] };
  }
  const activeEliminated = eliminated.filter(
    (candidate) => (firstRound.national[candidate.id] || 0) > 0
  );
  const transfer = {};
  for (const candidate of activeEliminated) {
    transfer[candidate.id] = clamp(
      (state.transfers[candidate.id] ?? state.defaultTransfer * 100) / 100,
      0,
      1
    );
  }

  const calculate = (shares) => {
    const first = topTwo[0].id;
    const second = topTwo[1].id;
    let firstShare = shares[first] || 0;
    let secondShare = shares[second] || 0;
    for (const candidate of activeEliminated) {
      const value = shares[candidate.id] || 0;
      firstShare += value * transfer[candidate.id];
      secondShare += value * (1 - transfer[candidate.id]);
    }
    const total = firstShare + secondShare;
    return {
      [first]: total ? firstShare / total : 0,
      [second]: total ? secondShare / total : 0,
    };
  };

  const national = calculate(firstRound.national);
  const provinces = firstRound.provinces.map((province) => {
    const shares = calculate(province.shares);
    const ranked = Object.entries(shares).sort((a, b) => b[1] - a[1]);
    return { ...province, shares, winner: ranked[0]?.[0] || null };
  });

  return { topTwo, eliminated: activeEliminated, national, provinces, transfer };
}

function render() {
  const first = buildFirstRound();
  const runoff = buildRunoff(first);
  state.first = first;
  state.runoff = runoff;

  const active = state.mapRound === "first" ? first : runoff;
  state.currentProvinces = new Map(
    active.provinces.map((province) => [province.geo_key, province])
  );
  state.map.update(state.currentProvinces);
  state.map.setSelected(state.selectedKey);
  buildLegend();

  const key = `${runoff.topTwo[0]?.id || "-"}|${runoff.topTwo[1]?.id || "-"}`;
  if (key !== state.transferKey) {
    state.transferKey = key;
    buildTransferControls();
  }

  updateBars(first, runoff);
  updateSummary(runoff);
  updateUrl();
  if (state.selectedKey) showProvinceDetail(state.selectedKey);
}

function barHtml(id, share, color, name) {
  return `<div class="bar-row">
    <span class="bar-label"><i class="dot" style="background:${color}"></i>${escapeHtml(
      name
    )}</span>
    <div class="bar-track">
      <div class="bar-fill" style="width:${(share * 100).toFixed(2)}%;background:${color}"></div>
      <span class="bar-marker"></span>
    </div>
    <span class="bar-value">${formatPct(share * 100)}</span>
  </div>`;
}

function updateBars(first, runoff) {
  const firstOrder = [...state.candidates].sort(
    (a, b) => (first.national[b.id] || 0) - (first.national[a.id] || 0)
  );
  $("first-bars").innerHTML = firstOrder
    .map((candidate) =>
      barHtml(
        candidate.id,
        first.national[candidate.id] || 0,
        candidate.color,
        candidateName(candidate.id)
      )
    )
    .join("");

  if (runoff.topTwo.length < 2) {
    $("runoff-bars").innerHTML = "";
    $("runoff-note").textContent = "2. tur hesaplanamadı.";
    return;
  }
  $("runoff-bars").innerHTML = runoff.topTwo
    .map((candidate) =>
      barHtml(
        candidate.id,
        runoff.national[candidate.id] || 0,
        candidate.color,
        candidateName(candidate.id)
      )
    )
    .join("");
  const eliminated = runoff.eliminated
    .map((candidate) => candidateName(candidate.id))
    .join(", ");
  $("runoff-note").textContent = eliminated
    ? `Transfer edilen adaylar: ${eliminated}. Kalan oylar ilk iki adaya paylaştırılır.`
    : "Transfer edilecek aday yok.";
}

function updateSummary(runoff) {
  const summary = $("summary");
  if (runoff.topTwo.length < 2) {
    summary.textContent = "2. tur hesaplanamadı";
    return;
  }
  const [first, second] = runoff.topTwo;
  const firstShare = runoff.national[first.id] || 0;
  const secondShare = runoff.national[second.id] || 0;
  const winner = firstShare >= secondShare ? first : second;
  const winnerShare = Math.max(firstShare, secondShare);
  const margin = Math.abs(firstShare - secondShare) * 100;
  summary.innerHTML = `<span class="dot" style="background:${winner.color}"></span>2. Tur: <strong>${escapeHtml(
    candidateName(winner.id)
  )}</strong> · ${formatPct(winnerShare * 100)} · fark ${formatPct(margin)}`;
}

function buildLegend() {
  const candidates =
    state.mapRound === "first"
      ? state.candidates
      : state.runoff?.topTwo?.length
      ? state.runoff.topTwo
      : state.candidates.slice(0, 2);
  $("president-legend").innerHTML = candidates
    .map(
      (candidate) =>
        `<span class="legend-item"><i style="background:${candidate.color}"></i>${escapeHtml(
          candidateName(candidate.id)
        )}</span>`
    )
    .join("");
}

function setRound(round) {
  state.mapRound = round;
  state.selectedKey = null;
  state.map?.setSelected(null);
  $("round-first").classList.toggle("active", round === "first");
  $("round-runoff").classList.toggle("active", round === "runoff");
  $("province-detail").innerHTML = "";
  hideTooltip();
  render();
}

function showTooltip({ title, leaders, meta }, event) {
  const tooltip = $("tooltip");
  const rows = leaders
    .map(({ id, share }) => {
      const candidate = state.byId.get(id);
      return `<div class="tip-row"><span class="dot" style="background:${
        candidate?.color || "#9e9e9e"
      }"></span>${escapeHtml(candidateName(id))}<span>${formatPct(
        share * 100
      )}</span></div>`;
    })
    .join("");
  tooltip.innerHTML = `<div class="tip-title">${title}</div>${rows}<div class="tip-meta">${meta}</div>`;
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

function handleHover(feature, event) {
  if (!feature) {
    hideTooltip();
    return;
  }
  const province = state.currentProvinces.get(
    normalizeName(feature.properties.shapeName)
  );
  if (!province) {
    hideTooltip();
    return;
  }
  const leaders = Object.entries(province.shares)
    .sort((a, b) => b[1] - a[1])
    .slice(0, state.mapRound === "first" ? 3 : 2)
    .map(([id, share]) => ({ id, share }));
  showTooltip(
    {
      title: feature.properties.shapeName,
      leaders,
      meta: `${formatPct(province.turnout * 100)} katılım · ${formatInt(
        province.valid_votes
      )} geçerli oy`,
    },
    event
  );
}

function handleSelect(feature) {
  if (!feature) return;
  const key = normalizeName(feature.properties.shapeName);
  state.selectedKey = state.selectedKey === key ? null : key;
  state.map.setSelected(state.selectedKey);
  if (state.selectedKey) showProvinceDetail(state.selectedKey);
  else $("province-detail").innerHTML = "";
}

function showProvinceDetail(key) {
  const province = state.currentProvinces.get(key);
  const detail = $("province-detail");
  if (!province) {
    detail.innerHTML = "";
    return;
  }
  const entries = Object.entries(province.shares).sort((a, b) => b[1] - a[1]);
  const rows = entries
    .map(([id, share]) => {
      const candidate = state.byId.get(id);
      return `<div class="detail-row no-seats">
        <span class="dot" style="background:${candidate?.color || "#9e9e9e"}"></span>
        <span>${escapeHtml(candidateName(id))}</span>
        <span>${formatPct(share * 100)}</span>
      </div>`;
    })
    .join("");

  const name = state.geoDisplay.get(key) || province.name;
  detail.innerHTML = `<div class="detail-head">
      <strong>${name}</strong>
      <span>${state.mapRound === "first" ? "1. Tur" : "2. Tur"} · ${formatPct(
    province.turnout * 100
  )} katılım</span>
    </div>
    ${rows}`;
}

function applyPollAverage() {
  const shares = presidentAggregate(state.pollData, 1);
  for (const candidate of state.candidates) {
    state.shares[candidate.id] = (shares[candidate.id] || 0) * 100;
  }
  normalizeShares();
  syncCandidateControls();
  state.selectedKey = null;
  state.map.setSelected(null);
  $("province-detail").innerHTML = "";
  hideTooltip();
  render();
}

function resetTo2023() {
  for (const candidate of state.candidates) {
    state.shares[candidate.id] =
      (state.data.president.first_round.national.shares[candidate.id] || 0) * 100;
    state.names[candidate.id] = candidate.short;
    state.transfers[candidate.id] = state.defaultTransfer * 100;
  }
  state.selectedKey = null;
  state.transferKey = null;
  $("province-detail").innerHTML = "";
  hideTooltip();
  syncCandidateControls();
  setRound("first");
}

function updateUrl() {
  const params = new URLSearchParams();
  for (const candidate of state.candidates) {
    const id = candidate.id;
    params.set(id.toLowerCase(), (state.shares[id] || 0).toFixed(1));
    params.set(`n${id}`, candidateName(id));
    params.set(`t${id}`, (state.transfers[id] ?? state.defaultTransfer * 100).toFixed(1));
  }
  params.set("m", state.mapRound);
  try {
    history.replaceState(null, "", `?${params.toString()}`);
  } catch {
    // file:// or a restricted context.
  }
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

function setGeneratedAt() {
  const value = state.data.meta.generated_at;
  if (!value) return;
  const formatted = new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
  $("generated-at").textContent = `Veri: ${formatted}`;
}

main().catch((error) => {
  console.error(error);
  const panel = document.querySelector(".map-panel");
  if (panel) {
    panel.innerHTML = `<div class="error">Veri yüklenemedi: ${error.message}</div>`;
  }
});
