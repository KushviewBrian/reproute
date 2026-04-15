from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.schemas.geocode import GeocodeResult

logger = logging.getLogger(__name__)


def _poc_fallback(query: str) -> list[GeocodeResult]:
    q = query.lower()
    known = {
        "indianapolis": (39.7683331, -86.1583502),
        "chicago": (41.8755616, -87.6244212),
        "detroit": (42.3315509, -83.0466403),
    }
    for name, (lat, lng) in known.items():
        if name in q:
            return [GeocodeResult(label=name.title(), lat=lat, lng=lng, bbox=None)]
    return [GeocodeResult(label=query, lat=39.7683331, lng=-86.1583502, bbox=None)]


async def geocode(
    query: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[list[GeocodeResult], bool]:
    settings = get_settings()

    if query is None and (lat is None or lng is None):
        return [], False
    if query is not None and not query.strip():
        return [], False

    params: dict = {"limit": 6}
    if query is not None:
        params["q"] = query
    else:
        params["lat"] = lat
        params["lon"] = lng

    try:
        async with httpx.AsyncClient(timeout=settings.geocode_timeout_seconds) as client:
            resp = await client.get(settings.geocode_worker_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.error("Geocode request failed url=%s error=%r", settings.geocode_worker_url, exc)
        if query is not None:
            return _poc_fallback(query), True
        return [], True

    features = payload.get("features", []) if isinstance(payload, dict) else []
    results: list[GeocodeResult] = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        if coords[0] is None or coords[1] is None:
            continue
        parts = [
            props.get("name") or props.get("label"),
            props.get("street"),
            props.get("city") or props.get("town") or props.get("village"),
            props.get("state"),
        ]
        label = ", ".join(p for p in parts if p) or query or f"{lat},{lng}"
        bbox = feature.get("bbox")
        results.append(GeocodeResult(label=label, lat=float(coords[1]), lng=float(coords[0]), bbox=bbox))

    logger.info("Geocode query=%r returned %d results degraded=False", query, len(results))
    return results, False
