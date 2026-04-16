from __future__ import annotations

import hashlib
import json
import math

import httpx

from app.core.config import get_settings
from app.utils.redis_client import redis_client


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
                "properties": {"summary": {"distance": int(distance_m), "duration": duration_s}},
            }
        ],
    }


async def get_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    return await get_route_multi([(origin_lat, origin_lng), (destination_lat, destination_lng)])


def _merge_route_features(features: list[dict]) -> dict:
    """Merge multiple ORS GeoJSON features into a single LineString feature."""
    all_coords: list[list[float]] = []
    total_distance = 0
    total_duration = 0
    for feat in features:
        coords = feat.get("geometry", {}).get("coordinates", [])
        if all_coords and coords:
            all_coords.extend(coords[1:])
        else:
            all_coords.extend(coords)
        summary = feat.get("properties", {}).get("summary", {})
        total_distance += summary.get("distance", 0)
        total_duration += summary.get("duration", 0)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": all_coords},
        "properties": {"summary": {"distance": int(total_distance), "duration": int(total_duration)}},
    }


async def get_route_multi(waypoints: list[tuple[float, float]]) -> dict:
    """Get a route through multiple waypoints (list of (lat, lng) tuples)."""
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
        # Mock: chain straight-line legs
        features = []
        for i in range(len(waypoints) - 1):
            lat1, lng1 = waypoints[i]
            lat2, lng2 = waypoints[i + 1]
            leg = _mock_route(lat1, lng1, lat2, lng2)
            features.append(leg["features"][0])
        merged = _merge_route_features(features)
        data = {"type": "FeatureCollection", "features": [merged]}
        await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
        return data

    url = f"{settings.ors_base_url.rstrip('/')}/v2/directions/driving-car/geojson"
    headers = {"Authorization": settings.ors_api_key, "Content-Type": "application/json"}
    coordinates = [[lng, lat] for lat, lng in waypoints]
    payload = {"coordinates": coordinates}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
    return data
