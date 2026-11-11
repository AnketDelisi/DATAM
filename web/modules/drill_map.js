import { normalizeName } from "./format.js";

const WIDTH = 800;
const HEIGHT = 380;

export function createDrillMap(
  svg,
  provincesGeo,
  ilceGeo,
  parties,
  {
    onProvinceHover,
    onIlceHover,
    onProvinceSelect,
    onIlceSelect,
    onZoomChange,
  } = {}
) {
  const d3 = globalThis.d3;
  const reduceMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  const duration = (value) => (reduceMotion ? 0 : value);
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const projection = d3
    .geoConicConformal()
    .parallels([35, 45])
    .rotate([-35, 0])
    .fitExtent([[18, 12], [782, 368]], provincesGeo);
  const path = d3.geoPath(projection);
  const colors = new Map(parties.map((party) => [party.id, party.color]));

  const zoomLayer = root.append("g");
  const provinceLayer = zoomLayer.append("g");
  const splitLayer = zoomLayer.append("g").attr("class", "electoral-layer").style("pointer-events", "none");
  const seatLayer = zoomLayer.append("g").attr("class", "seat-layer").style("pointer-events", "none");
  const ilceLayer = zoomLayer.append("g").style("display", "none");

  let provinceData = new Map();
  let ilceData = new Map();
  let districtWinners = new Map();
  let drilled = null;
  let selected = null;

  function renderSeats() {
    seatLayer.selectAll("*").remove();
    if (drilled) return;
    splitLayer.style("display", "block");
    const sortedParties = [...parties].sort(
      (left, right) =>
        left.seat_order - right.seat_order || left.id.localeCompare(right.id)
    );
    for (const [key, row] of provinceData) {
      if (!row.seats) continue;
      const feature = provinceFeatures.get(key);
      if (!feature) continue;
      const [cx, cy] = anchorFor(feature);
      const [[x0, y0], [x1, y1]] = path.bounds(feature);
      const width = Math.max(1, x1 - x0);
      const height = Math.max(1, y1 - y0);
      const order = [];
      const provinceParties = sortedParties
        .filter((party) => (row.scenario_seats?.[party.id] || 0) > 0)
        .sort(
          (left, right) =>
            (row.shares?.[right.id] || 0) - (row.shares?.[left.id] || 0) ||
            left.seat_order - right.seat_order
        );
      for (const party of provinceParties) {
        const count = row.scenario_seats[party.id] || 0;
        for (let index = 0; index < count; index += 1) order.push(party.id);
      }
      const total = Math.min(row.seats, order.length);
      if (!total) continue;
      const cols = Math.max(1, Math.ceil(Math.sqrt(total)));
      const rows = Math.ceil(total / cols);
      const size = Math.max(
        1.1,
        Math.min(5.2, (width * 0.62) / (cols * 1.2), (height * 0.62) / (rows * 1.2))
      );
      const spacing = size * 1.15;
      const startX = cx - ((cols - 1) * spacing) / 2;
      const startY = cy - ((rows - 1) * spacing) / 2;
      for (let index = 0; index < total; index += 1) {
        const x = startX + (index % cols) * spacing;
        const y = startY + Math.floor(index / cols) * spacing;
        seatLayer
          .append("rect")
          .attr("class", "seat-square")
          .attr("x", x - size / 2)
          .attr("y", y - size / 2)
          .attr("width", size)
          .attr("height", size)
          .attr("rx", 0.5)
          .attr("fill", colors.get(order[index]) || "#9e9e9e")
          .attr("stroke", "#fffdf8")
          .attr("stroke-width", 0.6);
      }
    }
  }

  function anchorFor(feature) {
    const centroid = path.centroid(feature);
    const inverse = projection.invert?.(centroid);
    if (inverse && d3.geoContains(feature, inverse)) return centroid;
    const geometry = feature.geometry;
    const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    let best = null;
    let bestArea = 0;
    for (const coordinates of polygons) {
      const polygon = { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates } };
      const area = path.area(polygon);
      if (area > bestArea) {
        bestArea = area;
        best = polygon;
      }
    }
    if (best) return projection(d3.geoCentroid(best));
    return centroid;
  }

  const provinceKey = (feature) => normalizeName(feature.properties.shapeName);
  const ilceKey = (feature) => feature.properties.shapeID;
  const ilceProvince = (feature) =>
    feature.properties.province_key ||
    normalizeName(feature.properties.province || "");

  const provinceFeatures = new Map(
    provincesGeo.features.map((feature) => [provinceKey(feature), feature])
  );

  const provincePaths = provinceLayer
    .selectAll("path")
    .data(provincesGeo.features)
    .join("path")
    .attr("class", "province-path")
    .attr("d", path)
    .attr("fill", "#dfe3e8")
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 0.6)
    .attr("vector-effect", "non-scaling-stroke")
    .attr("tabindex", 0)
    .attr("role", "button")
    .style("cursor", "pointer")
    .on("mouseenter", (event, feature) => onProvinceHover?.(feature, event))
    .on("mousemove", (event, feature) => onProvinceHover?.(feature, event))
    .on("mouseleave", () => onProvinceHover?.(null, null))
    .on("focus", (event, feature) => onProvinceHover?.(feature, event))
    .on("blur", () => onProvinceHover?.(null, null))
    .on("click", (event, feature) => {
      if (drilled) return;
      drill(provinceKey(feature));
      onProvinceSelect?.(feature);
    })
    .on("keydown", (event, feature) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      if (drilled) return;
      drill(provinceKey(feature));
      onProvinceSelect?.(feature);
    });

  const ilcePaths = ilceLayer
    .selectAll("path")
    .data(ilceGeo.features)
    .join("path")
    .attr("class", "ilce-path")
    .attr("d", path)
    .attr("fill", "#dfe3e8")
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 0.45)
    .attr("vector-effect", "non-scaling-stroke")
    .attr("tabindex", 0)
    .attr("role", "button")
    .style("cursor", "pointer")
    .on("mouseenter", (event, feature) => onIlceHover?.(feature, event))
    .on("mousemove", (event, feature) => onIlceHover?.(feature, event))
    .on("mouseleave", () => onIlceHover?.(null, null))
    .on("focus", (event, feature) => onIlceHover?.(feature, event))
    .on("blur", () => onIlceHover?.(null, null))
    .on("click", (event, feature) => {
      selected = ilceKey(feature);
      paintSelection();
      onIlceSelect?.(feature);
    })
    .on("keydown", (event, feature) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      selected = ilceKey(feature);
      paintSelection();
      onIlceSelect?.(feature);
    });

  function drill(key) {
    const feature = provinceFeatures.get(key);
    if (!feature) return;
    drilled = key;
    selected = null;
    seatLayer.style("display", "none");
    splitLayer.style("display", "none");
    const [[x0, y0], [x1, y1]] = path.bounds(feature);
    const scale = Math.min(WIDTH / (x1 - x0), HEIGHT / (y1 - y0)) * 0.82;
    const tx = WIDTH / 2 - scale * ((x0 + x1) / 2);
    const ty = HEIGHT / 2 - scale * ((y0 + y1) / 2);

    ilcePaths.style("display", (row) => (ilceProvince(row) === key ? null : "none"));
    ilceLayer
      .style("display", "block")
      .style("pointer-events", "all")
      .style("opacity", 0)
      .transition()
      .duration(duration(450))
      .style("opacity", 1);
    provinceLayer.transition().duration(duration(500)).style("opacity", 0);
    provincePaths.style("pointer-events", "none");
    zoomLayer
      .transition()
      .duration(duration(700))
      .ease(d3.easeCubicInOut)
      .attr("transform", `translate(${tx},${ty}) scale(${scale})`);
    onZoomChange?.(key);
  }

  function reset() {
    drilled = null;
    selected = null;
    splitLayer.style("display", "block");
    seatLayer.style("display", "block");
    renderSeats();
    provinceLayer.transition().duration(duration(450)).style("opacity", 1);
    provincePaths.style("pointer-events", "all");
    ilceLayer
      .transition()
      .duration(duration(300))
      .style("opacity", 0)
      .on("end", () => {
        if (drilled) return;
        ilceLayer.style("display", "none").style("pointer-events", "none");
        ilcePaths.style("display", "none");
      });
    zoomLayer
      .transition()
      .duration(duration(650))
      .ease(d3.easeCubicInOut)
      .attr("transform", "translate(0,0) scale(1)");
    onZoomChange?.(null);
  }

  function paintSelection() {
    provincePaths.attr("stroke", (feature) =>
      drilled === null && selected === provinceKey(feature) ? "#111827" : "#ffffff"
    );
    ilcePaths.attr("stroke", (feature) =>
      selected === ilceKey(feature) ? "#111827" : "#ffffff"
    );
  }

  function update(nextProvinceData, nextIlceData, splitGeo, nextDistrictWinners) {
    provinceData = nextProvinceData;
    ilceData = nextIlceData;
    districtWinners = nextDistrictWinners || new Map();
    splitLayer
      .selectAll("path")
      .data(splitGeo?.features || [], (feature) => feature.properties.district_id)
      .join("path")
      .attr("class", "electoral-path")
      .attr("d", path)
      .attr("fill", (feature) => {
        const winner = districtWinners.get(feature.properties.district_id);
        return winner ? colors.get(winner) || "#9e9e9e" : "#dfe3e8";
      })
      .attr("stroke", "#fffdf8")
      .attr("stroke-width", 1.2)
      .attr("vector-effect", "non-scaling-stroke");
    provincePaths.attr("fill", (feature) => {
      const row = provinceData.get(provinceKey(feature));
      return row?.winner ? colors.get(row.winner) || "#9e9e9e" : "#dfe3e8";
    });
    ilcePaths.attr("fill", (feature) => {
      const row = ilceData.get(ilceKey(feature));
      return row?.winner ? colors.get(row.winner) || "#9e9e9e" : "#dfe3e8";
    });
    paintSelection();
    renderSeats();
  }

  function setSelected(value) {
    selected = value;
    paintSelection();
  }

  return {
    update,
    reset,
    drill,
    setSelected,
    get drilled() {
      return drilled;
    },
  };
}
