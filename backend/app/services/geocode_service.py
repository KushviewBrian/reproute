from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.schemas.geocode import GeocodeResult


async def geocode(query: str | None = None, lat: float | None = None, lng: float | None = None) -> tuple[list[GeocodeResult], bool]:
    settings = get_settings()
    if query is None and (lat is None or lng is None):
        return [], False
    if query is not None and not query.strip():
        return [], False

    if query is not None:
        params = {"q": query, "limit": 5}
    else:
        params = {"lat": lat, "lon": lng}

    degraded = False
    try:
        async with httpx.AsyncClient(timeout=settings.geocode_timeout_seconds) as client:
            resp = await client.get(settings.geocode_worker_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return [], True

    features = payload.get("features", []) if isinstance(payload, dict) else []
    results: list[GeocodeResult] = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        if coords[0] is None or coords[1] is None:
            continue
        label = props.get("name") or props.get("label") or query or f"{lat},{lng}"
        bbox = feature.get("bbox")
        results.append(GeocodeResult(label=label, lat=float(coords[1]), lng=float(coords[0]), bbox=bbox))

    return results, degraded
