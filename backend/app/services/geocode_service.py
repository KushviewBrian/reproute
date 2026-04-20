from __future__ import annotations

import asyncio
import hashlib
import json
import logging

import httpx

from app.core.config import get_settings
from app.schemas.geocode import GeocodeResult
from app.utils.http_clients import get_geocode_client
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

# Retry policy for Photon geocode upstream calls.
# Transient errors (timeout, network, 5xx) are retried once before falling back
# to the POC fallback so the user always gets a response.
_GEOCODE_MAX_ATTEMPTS = 2
_GEOCODE_RETRY_DELAY_SECONDS = 0.5


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


def _is_transient_geocode_error(exc: BaseException) -> bool:
    """Return True for errors that are safe to retry against Photon."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


def _geocode_cache_key(url: str, params: dict) -> str:
    payload = json.dumps({"url": url, "params": params}, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"geocode:{digest}"


async def _fetch_geocode(
    url: str,
    params: dict,
    timeout: int,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Fetch geocode results from Photon with up to _GEOCODE_MAX_ATTEMPTS attempts.

    - Transient errors are retried after _GEOCODE_RETRY_DELAY_SECONDS.
    - 4xx errors are terminal and raised immediately.
    - Raises the last exception when all attempts are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, _GEOCODE_MAX_ATTEMPTS + 1):
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=timeout) as ephemeral_client:
                    resp = await ephemeral_client.get(url, params=params)
                    resp.raise_for_status()
                    return resp.json()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except BaseException as exc:
            last_exc = exc
            if not _is_transient_geocode_error(exc):
                raise
            if attempt < _GEOCODE_MAX_ATTEMPTS:
                logger.warning(
                    "geocode_retry attempt=%d/%d error=%r url=%s",
                    attempt,
                    _GEOCODE_MAX_ATTEMPTS,
                    exc,
                    url,
                )
                await asyncio.sleep(_GEOCODE_RETRY_DELAY_SECONDS)
            else:
                logger.critical(
                    "geocode_degraded_fallback attempts_exhausted=%d error=%r url=%s",
                    _GEOCODE_MAX_ATTEMPTS,
                    exc,
                    url,
                )
    assert last_exc is not None
    raise last_exc


async def geocode(
    query: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[list[GeocodeResult], bool]:
    """
    Geocode a query string or reverse-geocode (lat, lng).

    Returns (results, degraded).  degraded=True means the Photon upstream was
    unavailable and results came from the built-in POC fallback.
    """
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

    cache_key = _geocode_cache_key(settings.geocode_worker_url, params)
    cached = await redis_client.get(cache_key)
    if cached:
        try:
            payload = json.loads(cached)
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
                results.append(
                    GeocodeResult(label=label, lat=float(coords[1]), lng=float(coords[0]), bbox=bbox),
                )
            return results, False
        except Exception:
            pass

    try:
        payload = await _fetch_geocode(
            settings.geocode_worker_url,
            params,
            settings.geocode_timeout_seconds,
            client=get_geocode_client(),
        )
        await redis_client.set(cache_key, json.dumps(payload), ex=7 * 24 * 60 * 60)
    except Exception as exc:
        logger.error(
            "geocode_all_attempts_failed url=%s error=%r — using POC fallback",
            settings.geocode_worker_url,
            exc,
        )
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

    logger.info("geocode query=%r returned %d results degraded=False", query, len(results))
    return results, False
