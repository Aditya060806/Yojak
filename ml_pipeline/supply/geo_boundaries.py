# ml_pipeline/supply/geo_boundaries.py

"""
India state boundaries for the workforce map, from the Survey of India index map
(via DataMeet, data/raw/external/boundaries/India-States.*).

Writes a simplified GeoJSON (WGS84) to app/frontend/public/geo/india-states.json with
each feature's `name` set to the GeoNames state name used everywhere else in Yojak.

Notes carried into the file's metadata:
  * The index map predates the 2019 reorganisation: Jammu & Kashmir and Ladakh are one
    polygon (shown with Jammu and Kashmir's data; Ladakh has very few postings).
  * Dadra & Nagar Haveli and Daman & Diu are separate polygons, both carrying the merged
    UT's name.

    python -m ml_pipeline.supply.geo_boundaries
"""

from __future__ import annotations

import json
import sys

import shapefile
from shapely.geometry import mapping, shape

from app.core.settings import PROJECT_ROOT, get_settings

NAMES = {
    "Andaman & Nicobar Island": "Andaman and Nicobar",
    "Arunanchal Pradesh": "Arunachal Pradesh",
    "Dadara & Nagar Havelli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "NCT of Delhi": "Delhi",
}
TOLERANCE = 0.02  # degrees (~2 km): plenty for a national choropleth


def _round(coords, nd=3):
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        return [round(c, nd) for c in coords]
    return [_round(c, nd) for c in coords]


def build() -> dict:
    src = get_settings().external_data_dir / "boundaries" / "India-States"
    r = shapefile.Reader(str(src))
    feats = []
    for rec, shp in zip(r.records(), r.shapes(), strict=True):
        raw = rec[0].strip()
        geom = shape(shp.__geo_interface__).simplify(TOLERANCE, preserve_topology=True)
        g = mapping(geom)
        feats.append({"type": "Feature", "properties": {"name": NAMES.get(raw, raw), "source_name": raw},
                      "geometry": {"type": g["type"], "coordinates": _round(g["coordinates"])}})
    return {"type": "FeatureCollection", "features": feats,
            "metadata": {"source": "Survey of India index map via DataMeet (github.com/datameet/maps)",
                         "notes": ["Jammu & Kashmir and Ladakh are a single polygon (pre-2019 map); it shows "
                                   "Jammu and Kashmir's figures.",
                                   "Boundaries follow the Survey of India."],
                         "simplified_tolerance_deg": TOLERANCE}}


def main() -> int:
    out = PROJECT_ROOT / "app" / "frontend" / "public" / "geo" / "india-states.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{out} ({out.stat().st_size / 1024:.0f} KB, {len(data['features'])} features)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
