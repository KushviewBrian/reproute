from __future__ import annotations


def linestring_wkt_from_geojson(geometry: dict) -> str:
    coords = geometry.get("coordinates", [])
    pairs = []
    for lng, lat in coords:
        pairs.append(f"{lng} {lat}")
    joined = ", ".join(pairs)
    return f"LINESTRING({joined})"
