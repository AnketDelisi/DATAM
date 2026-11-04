"""Reverse GeoJSON rings for D3's spherical winding convention.

    uv run python pipeline/rewind_geojson.py

geoBoundaries ships exterior rings in the opposite winding to what d3-geo
expects, so d3.geoBounds sees every province as the whole sphere. Reversing
each ring fixes the projection and the choropleth. Run once after replacing
web/geo/tr-provinces.geojson.
"""

from __future__ import annotations

import json
from pathlib import Path

GEO = Path(__file__).resolve().parents[1] / "web" / "geo" / "tr-provinces.geojson"


def reverse_rings(coords):
    return [ring[::-1] for ring in coords]


def main() -> None:
    data = json.loads(GEO.read_text(encoding="utf-8"))
    for feature in data["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            geometry["coordinates"] = reverse_rings(geometry["coordinates"])
        elif geometry["type"] == "MultiPolygon":
            geometry["coordinates"] = [
                reverse_rings(polygon) for polygon in geometry["coordinates"]
            ]
    GEO.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"rewound {len(data['features'])} features -> {GEO}")


if __name__ == "__main__":
    main()
