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
  const seatLayer = zoomLayer.append("g").attr("class", "seat-layer").style("pointer-events", "none");
  const ilceLayer = zoomLayer.append("g").style("display", "none");

  let provinceData = new Map();
  let ilceData = new Map();
  let drilled = null;
  let selected = null;

  function renderSeats() {
    seatLayer.selectAll("*").remove();
    if (drilled) return;
    for (const [key, row] of provinceData) {
      if (!row.seats) continue;
      const feature = provinceFeatures.get(key);
      if (!feature) continue;
      const [cx, cy] = anchorFor(feature);
      seatLayer
        .append("text")
        .attr("x", cx)
        .attr("y", cy + 2)
        .attr("text-anchor", "middle")
        .attr("class", "seat-badge")
        .attr("fill", "#171714")
        .attr("stroke", "#fffdf8")
        .attr("stroke-width", 2.2)
        .attr("paint-order", "stroke")
        .attr("font-size", row.seats >= 10 ? 7 : 6)
        .attr("font-weight", 700)
        .text(row.seats);
    }
  }

  function colorsFor(id) {
    return colors.get(id) || "#9e9e9e";
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

  function update(nextProvinceData, nextIlceData) {
    provinceData = nextProvinceData;
    ilceData = nextIlceData;
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
