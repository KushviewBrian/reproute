from __future__ import annotations

import hashlib
import json

import httpx

from app.core.config import get_settings
from app.utils.redis_client import redis_client


def _route_cache_key(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> str:
    raw = f"{origin_lat:.7f}:{origin_lng:.7f}:{destination_lat:.7f}:{destination_lng:.7f}"
    return "route:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    settings = get_settings()
    key = _route_cache_key(origin_lat, origin_lng, destination_lat, destination_lng)
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    url = f"{settings.ors_base_url.rstrip('/')}/v2/directions/driving-car/geojson"
    headers = {"Authorization": settings.ors_api_key, "Content-Type": "application/json"}
    payload = {"coordinates": [[origin_lng, origin_lat], [destination_lng, destination_lat]]}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    await redis_client.set(key, json.dumps(data), ex=settings.route_cache_ttl_seconds)
    return data
