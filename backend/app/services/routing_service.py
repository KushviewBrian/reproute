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
    settings = get_settings()
    key = _route_cache_key(origin_lat, origin_lng, destination_lat, destination_lng)
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    if settings.poc_mode and not settings.ors_api_key:
        data = _mock_route(origin_lat, origin_lng, destination_lat, destination_lng)
        await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
        return data

    url = f"{settings.ors_base_url.rstrip('/')}/v2/directions/driving-car/geojson"
    headers = {"Authorization": settings.ors_api_key, "Content-Type": "application/json"}
    payload = {"coordinates": [[origin_lng, origin_lat], [destination_lng, destination_lat]]}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
    return data
