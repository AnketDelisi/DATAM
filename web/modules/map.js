import { normalizeName } from "./format.js";

export function createMap(
  svg,
  geojson,
  parties,
  {
    keyFn = (feature) => normalizeName(feature.properties.shapeName),
    onHover,
    onSelect,
  } = {}
) {
  const d3 = globalThis.d3;
  const root = d3.select(svg);
  root.selectAll("*").remove();

  const projection = d3
    .geoConicConformal()
    .parallels([35, 45])
    .rotate([-35, 0])
    .fitExtent(
      [
        [18, 12],
        [782, 368],
      ],
      geojson
    );
  const path = d3.geoPath(projection);

  const colors = new Map(parties.map((party) => [party.id, party.color]));
  const paths = root
    .append("g")
    .selectAll("path")
    .data(geojson.features)
    .join("path")
    .attr("d", path)
    .attr("fill", "#dfe3e8")
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 0.6)
    .attr("vector-effect", "non-scaling-stroke")
    .attr("tabindex", 0)
    .attr("role", "button")
    .style("cursor", "pointer")
    .on("mouseenter", (event, feature) => onHover?.(feature, event))
    .on("mousemove", (event, feature) => onHover?.(feature, event))
    .on("mouseleave", () => onHover?.(null, null))
    .on("focus", (event, feature) => onHover?.(feature, event))
    .on("blur", () => onHover?.(null, null))
    .on("click", (event, feature) => onSelect?.(feature))
    .on("keydown", (event, feature) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect?.(feature);
      }
    });

  function setParties(nextParties) {
    colors.clear();
    for (const party of nextParties) colors.set(party.id, party.color);
  }

  function update(dataMap) {
    paths.attr("fill", (feature) => {
      const row = dataMap.get(keyFn(feature));
      if (!row?.winner) return "#dfe3e8";
      return colors.get(row.winner) || "#9e9e9e";
    });
  }

  function setSelected(geoKey) {
    paths
      .attr("stroke", (feature) => (keyFn(feature) === geoKey ? "#111827" : "#ffffff"))
      .attr("stroke-width", (feature) => (keyFn(feature) === geoKey ? 1.8 : 0.6));
  }

  return { update, setSelected, setParties, paths };
}
