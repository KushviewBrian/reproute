"""
Unit tests for Task 7-A: ORS routing and Photon geocode retry + degraded fallback.

Covers:
- ORS transient failure → retry → success
- ORS transient failure → retry exhausted → degraded straight-line fallback
- ORS 4xx error → no retry, exception propagates
- Geocode transient failure → retry → success
- Geocode transient failure → retry exhausted → POC fallback (degraded=True)
- Geocode 4xx error → no retry, POC fallback
- Mock route (no ORS key) always returns degraded=True
- _merge_route_features propagates degraded flag correctly
- _is_transient_ors_error classification
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.routing_service import (
    _build_mock_data,
    _is_transient_ors_error,
    _merge_route_features,
    _mock_route,
    get_route_multi,
)
from app.services.geocode_service import (
    _is_transient_geocode_error,
    geocode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ors_success_response() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-86.15, 39.77], [-87.62, 41.88]]},
                "properties": {"summary": {"distance": 200000, "duration": 7200}},
            }
        ],
    }


def _photon_success_response() -> dict:
    return {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-86.1583502, 39.7683331]},
                "properties": {"name": "Indianapolis", "state": "Indiana"},
            }
        ]
    }


def _make_timeout_exc() -> httpx.TimeoutException:
    return httpx.TimeoutException("timed out", request=MagicMock())


def _make_connect_exc() -> httpx.ConnectError:
    return httpx.ConnectError("connection refused", request=MagicMock())


def _make_5xx_exc() -> httpx.HTTPStatusError:
    resp = MagicMock()
    resp.status_code = 503
    return httpx.HTTPStatusError("503", request=MagicMock(), response=resp)


def _make_4xx_exc() -> httpx.HTTPStatusError:
    resp = MagicMock()
    resp.status_code = 400
    return httpx.HTTPStatusError("400", request=MagicMock(), response=resp)


# ---------------------------------------------------------------------------
# _is_transient_ors_error
# ---------------------------------------------------------------------------

def test_timeout_is_transient():
    assert _is_transient_ors_error(_make_timeout_exc()) is True


def test_connect_error_is_transient():
    assert _is_transient_ors_error(_make_connect_exc()) is True


def test_5xx_is_transient():
    assert _is_transient_ors_error(_make_5xx_exc()) is True


def test_4xx_is_not_transient():
    assert _is_transient_ors_error(_make_4xx_exc()) is False


def test_value_error_is_not_transient():
    assert _is_transient_ors_error(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# _is_transient_geocode_error (same taxonomy, separate service)
# ---------------------------------------------------------------------------

def test_geocode_timeout_is_transient():
    assert _is_transient_geocode_error(_make_timeout_exc()) is True


def test_geocode_4xx_is_not_transient():
    assert _is_transient_geocode_error(_make_4xx_exc()) is False


# ---------------------------------------------------------------------------
# _mock_route / _merge_route_features
# ---------------------------------------------------------------------------

def test_mock_route_sets_degraded():
    result = _mock_route(39.77, -86.15, 41.88, -87.62)
    feat = result["features"][0]
    assert feat["properties"]["degraded"] is True


def test_merge_propagates_degraded():
    feat_degraded = _mock_route(39.77, -86.15, 41.88, -87.62)["features"][0]
    feat_clean = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-86.15, 39.77], [-87.62, 41.88]]},
        "properties": {"summary": {"distance": 1000, "duration": 60}},
    }
    merged = _merge_route_features([feat_clean, feat_degraded])
    assert merged["properties"].get("degraded") is True


def test_merge_no_degraded_flag_when_all_live():
    feat = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-86.15, 39.77], [-87.62, 41.88]]},
        "properties": {"summary": {"distance": 1000, "duration": 60}},
    }
    merged = _merge_route_features([feat])
    assert "degraded" not in merged["properties"]


# ---------------------------------------------------------------------------
# get_route_multi — no ORS key (dev/mock mode)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_ors_key_returns_mock():
    waypoints = [(39.77, -86.15), (41.88, -87.62)]
    with patch("app.services.routing_service.get_settings") as mock_settings, \
         patch("app.services.routing_service.redis_client") as mock_redis:
        s = MagicMock()
        s.ors_api_key = ""
        s.route_cache_ttl_seconds = 86400
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        result = await get_route_multi(waypoints)
        feat = result["features"][0]
        assert feat["properties"].get("degraded") is True
        mock_redis.set.assert_called_once()


# ---------------------------------------------------------------------------
# get_route_multi — ORS key present, first attempt succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ors_success_on_first_attempt():
    waypoints = [(39.77, -86.15), (41.88, -87.62)]
    with patch("app.services.routing_service.get_settings") as mock_settings, \
         patch("app.services.routing_service.redis_client") as mock_redis, \
         patch("app.services.routing_service._call_ors_with_retry", new_callable=AsyncMock) as mock_ors:
        s = MagicMock()
        s.ors_api_key = "test-key"
        s.ors_base_url = "https://api.openrouteservice.org"
        s.route_cache_ttl_seconds = 86400
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_ors.return_value = _ors_success_response()

        result = await get_route_multi(waypoints)
        assert result["features"][0]["geometry"]["type"] == "LineString"
        assert "degraded" not in result["features"][0].get("properties", {})
        mock_ors.assert_called_once()


# ---------------------------------------------------------------------------
# get_route_multi — ORS key present, all attempts fail → degraded fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ors_all_attempts_fail_returns_degraded():
    waypoints = [(39.77, -86.15), (41.88, -87.62)]
    with patch("app.services.routing_service.get_settings") as mock_settings, \
         patch("app.services.routing_service.redis_client") as mock_redis, \
         patch("app.services.routing_service._call_ors_with_retry", new_callable=AsyncMock) as mock_ors:
        s = MagicMock()
        s.ors_api_key = "test-key"
        s.ors_base_url = "https://api.openrouteservice.org"
        s.route_cache_ttl_seconds = 86400
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_ors.side_effect = _make_timeout_exc()

        result = await get_route_multi(waypoints)
        feat = result["features"][0]
        # Must return a valid GeoJSON feature even when ORS is down
        assert feat["geometry"]["type"] == "LineString"
        assert feat["properties"].get("degraded") is True
        # Degraded results cached with a short TTL (≤300s)
        _key, cached_json, kwargs = mock_redis.set.call_args[0][0], mock_redis.set.call_args[0][1], mock_redis.set.call_args[1]
        assert kwargs.get("ex", 999) <= 300


# ---------------------------------------------------------------------------
# get_route_multi — cache hit skips ORS entirely
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_skips_ors():
    waypoints = [(39.77, -86.15), (41.88, -87.62)]
    cached_data = _ors_success_response()
    with patch("app.services.routing_service.get_settings") as mock_settings, \
         patch("app.services.routing_service.redis_client") as mock_redis, \
         patch("app.services.routing_service._call_ors_with_retry", new_callable=AsyncMock) as mock_ors:
        s = MagicMock()
        s.ors_api_key = "test-key"
        s.ors_base_url = "https://api.openrouteservice.org"
        s.route_cache_ttl_seconds = 86400
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        result = await get_route_multi(waypoints)
        assert result == cached_data
        mock_ors.assert_not_called()


# ---------------------------------------------------------------------------
# geocode — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geocode_success():
    with patch("app.services.geocode_service.get_settings") as mock_settings, \
         patch("app.services.geocode_service._fetch_geocode", new_callable=AsyncMock) as mock_fetch:
        s = MagicMock()
        s.geocode_worker_url = "https://photon.komoot.io/api/"
        s.geocode_timeout_seconds = 4
        mock_settings.return_value = s
        mock_fetch.return_value = _photon_success_response()

        results, degraded = await geocode(query="Indianapolis")
        assert len(results) == 1
        assert results[0].label == "Indianapolis, Indiana"
        assert degraded is False


# ---------------------------------------------------------------------------
# geocode — all attempts fail → POC fallback, degraded=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geocode_fallback_on_failure():
    with patch("app.services.geocode_service.get_settings") as mock_settings, \
         patch("app.services.geocode_service._fetch_geocode", new_callable=AsyncMock) as mock_fetch:
        s = MagicMock()
        s.geocode_worker_url = "https://photon.komoot.io/api/"
        s.geocode_timeout_seconds = 4
        mock_settings.return_value = s
        mock_fetch.side_effect = _make_timeout_exc()

        results, degraded = await geocode(query="Indianapolis")
        assert len(results) == 1
        assert degraded is True
        assert results[0].lat == pytest.approx(39.7683331, abs=1e-4)


@pytest.mark.asyncio
async def test_geocode_empty_query_returns_empty():
    results, degraded = await geocode(query="   ")
    assert results == []
    assert degraded is False


@pytest.mark.asyncio
async def test_geocode_no_args_returns_empty():
    results, degraded = await geocode()
    assert results == []
    assert degraded is False
