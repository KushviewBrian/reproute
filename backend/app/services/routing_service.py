from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math

import httpx

from app.core.config import get_settings
from app.utils.http_clients import get_ors_client
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

# Retry policy for ORS upstream calls.
# Attempt up to _ORS_MAX_ATTEMPTS times, waiting _ORS_RETRY_DELAY_SECONDS between
# attempts.  Only transient errors (timeout, network, 5xx) are retried; 4xx errors
# are terminal and bubble up immediately.
_ORS_MAX_ATTEMPTS = 2
_ORS_RETRY_DELAY_SECONDS = 1.0


def _route_cache_key(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> str:
    raw = f"{origin_lat:.7f}:{origin_lng:.7f}:{destination_lat:.7f}:{destination_lng:.7f}"
    return "route:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _estimate_distance_m(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> float:
    r = 6371000.0
    lat1 = math.radians(origin_lat)
    lat2 = math.radians(destination_lat)
    d_lat = math.radians(destination_lat - origin_lat)
    d_lng = math.radians(destination_lng - origin_lng)
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _mock_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    """Build a straight-line fallback route. Sets degraded=True on the feature properties."""
    distance_m = _estimate_distance_m(origin_lat, origin_lng, destination_lat, destination_lng)
    duration_s = int(distance_m / 13.4)  # ~30 mph average urban speed
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[origin_lng, origin_lat], [destination_lng, destination_lat]],
                },
                "properties": {
                    "summary": {"distance": int(distance_m), "duration": duration_s},
                    "degraded": True,
                },
            }
        ],
    }


def _is_transient_ors_error(exc: BaseException) -> bool:
    """Return True for errors that are safe to retry against ORS."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


async def _call_ors_with_retry(
    url: str,
    headers: dict,
    payload: dict,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    POST to ORS with up to _ORS_MAX_ATTEMPTS attempts.

    - Transient errors (timeout, network, 5xx) are retried after _ORS_RETRY_DELAY_SECONDS.
    - 4xx client errors are terminal and raised immediately without retry.
    - Raises the last exception when all attempts are exhausted so the caller can
      decide whether to fall back to the mock route.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, _ORS_MAX_ATTEMPTS + 1):
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=10) as ephemeral_client:
                    resp = await ephemeral_client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        except BaseException as exc:
            last_exc = exc
            if not _is_transient_ors_error(exc):
                # 4xx or unexpected error — do not retry
                raise
            if attempt < _ORS_MAX_ATTEMPTS:
                logger.warning(
                    "ors_retry attempt=%d/%d error=%r url=%s",
                    attempt,
                    _ORS_MAX_ATTEMPTS,
                    exc,
                    url,
                )
                await asyncio.sleep(_ORS_RETRY_DELAY_SECONDS)
            else:
                logger.critical(
                    "ors_degraded_fallback attempts_exhausted=%d error=%r url=%s",
                    _ORS_MAX_ATTEMPTS,
                    exc,
                    url,
                )
    assert last_exc is not None
    raise last_exc


async def get_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    return await get_route_multi([(origin_lat, origin_lng), (destination_lat, destination_lng)])


def _merge_route_features(features: list[dict]) -> dict:
    """Merge multiple ORS GeoJSON features into a single LineString feature."""
    all_coords: list[list[float]] = []
    total_distance = 0
    total_duration = 0
    degraded = False
    for feat in features:
        coords = feat.get("geometry", {}).get("coordinates", [])
        if all_coords and coords:
            all_coords.extend(coords[1:])
        else:
            all_coords.extend(coords)
        summary = feat.get("properties", {}).get("summary", {})
        total_distance += summary.get("distance", 0)
        total_duration += summary.get("duration", 0)
        if feat.get("properties", {}).get("degraded"):
            degraded = True
    props: dict = {"summary": {"distance": int(total_distance), "duration": int(total_duration)}}
    if degraded:
        props["degraded"] = True
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": all_coords},
        "properties": props,
    }


def _build_mock_data(waypoints: list[tuple[float, float]], cache_ttl: int) -> tuple[dict, int]:
    """Build a mock straight-line route for all waypoint legs. Returns (data, ttl)."""
    features = []
    for i in range(len(waypoints) - 1):
        lat1, lng1 = waypoints[i]
        lat2, lng2 = waypoints[i + 1]
        leg = _mock_route(lat1, lng1, lat2, lng2)
        features.append(leg["features"][0])
    merged = _merge_route_features(features)
    data = {"type": "FeatureCollection", "features": [merged]}
    # Cache degraded results for a shorter window so a healthy ORS response
    # can replace them quickly on the next request.
    ttl = min(300, cache_ttl)
    return data, ttl


async def get_route_multi(waypoints: list[tuple[float, float]]) -> dict:
    """
    Get a route through multiple waypoints (list of (lat, lng) tuples).

    Behaviour:
    - With ORS key: attempts ORS up to _ORS_MAX_ATTEMPTS times with backoff.
    - On ORS transient failure after all retries: falls back to straight-line mock
      and sets ``properties.degraded = True`` on the merged feature so callers can
      surface a warning to the user.
    - Without ORS key (dev/test): always uses mock straight-line route.
    """
    if len(waypoints) < 2:
        raise ValueError("At least 2 waypoints required")

    settings = get_settings()

    # Build a cache key from all waypoints
    raw = ":".join(f"{lat:.7f},{lng:.7f}" for lat, lng in waypoints)
    key = "route:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    if not settings.ors_api_key:
        # No ORS key configured — use mock straight-line route (dev/test mode)
        data, ttl = _build_mock_data(waypoints, settings.route_cache_ttl_seconds)
        await redis_client.set(key, json.dumps(data), ex=ttl)
        return data

    url = f"{settings.ors_base_url.rstrip('/')}/v2/directions/driving-car/geojson"
    headers = {"Authorization": settings.ors_api_key, "Content-Type": "application/json"}
    coordinates = [[lng, lat] for lat, lng in waypoints]
    payload = {"coordinates": coordinates}

    try:
        data = await _call_ors_with_retry(url, headers, payload, client=get_ors_client())
        await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
        return data
    except BaseException as exc:
        # All retry attempts exhausted — degrade gracefully to straight-line mock
        # so the user still receives a route rather than a 500 error.
        logger.critical(
            "ors_all_attempts_failed error=%r — serving degraded straight-line route to user", exc
        )
        data, ttl = _build_mock_data(waypoints, settings.route_cache_ttl_seconds)
        await redis_client.set(key, json.dumps(data), ex=ttl)
        return data
