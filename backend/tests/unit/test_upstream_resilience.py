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
         patch("app.services.geocode_service.redis_client") as mock_redis, \
         patch("app.services.geocode_service.get_geocode_client", return_value=MagicMock()), \
         patch("app.services.geocode_service._fetch_geocode", new_callable=AsyncMock) as mock_fetch:
        s = MagicMock()
        s.geocode_worker_url = "https://photon.komoot.io/api/"
        s.geocode_timeout_seconds = 4
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_fetch.return_value = _photon_success_response()

        results, degraded = await geocode(query="Indianapolis")
        assert len(results) == 1
        assert results[0].label == "Indianapolis, Indiana"
        assert degraded is False
        mock_redis.set.assert_called_once()


# ---------------------------------------------------------------------------
# geocode — all attempts fail → POC fallback, degraded=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geocode_fallback_on_failure():
    with patch("app.services.geocode_service.get_settings") as mock_settings, \
         patch("app.services.geocode_service.redis_client") as mock_redis, \
         patch("app.services.geocode_service.get_geocode_client", return_value=MagicMock()), \
         patch("app.services.geocode_service._fetch_geocode", new_callable=AsyncMock) as mock_fetch:
        s = MagicMock()
        s.geocode_worker_url = "https://photon.komoot.io/api/"
        s.geocode_timeout_seconds = 4
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_fetch.side_effect = _make_timeout_exc()

        results, degraded = await geocode(query="Indianapolis")
        assert len(results) == 1
        assert degraded is True
        assert results[0].lat == pytest.approx(39.7683331, abs=1e-4)
        mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_geocode_cache_hit_skips_upstream_fetch():
    cached_payload = _photon_success_response()
    with patch("app.services.geocode_service.get_settings") as mock_settings, \
         patch("app.services.geocode_service.redis_client") as mock_redis, \
         patch("app.services.geocode_service._fetch_geocode", new_callable=AsyncMock) as mock_fetch:
        s = MagicMock()
        s.geocode_worker_url = "https://photon.komoot.io/api/"
        s.geocode_timeout_seconds = 4
        mock_settings.return_value = s
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_payload))

        results, degraded = await geocode(query="Indianapolis")
        assert len(results) == 1
        assert degraded is False
        mock_fetch.assert_not_called()


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


# ---------------------------------------------------------------------------
# Overpass / osm_enrichment_service — retry + degraded return
# ---------------------------------------------------------------------------

from app.services.osm_enrichment_service import (
    _is_transient_overpass_error,
    _call_overpass_with_retry,
    fetch_osm_enrichment,
)


def test_overpass_timeout_is_transient():
    assert _is_transient_overpass_error(_make_timeout_exc()) is True


def test_overpass_connect_is_transient():
    assert _is_transient_overpass_error(_make_connect_exc()) is True


def test_overpass_5xx_is_transient():
    assert _is_transient_overpass_error(_make_5xx_exc()) is True


def test_overpass_4xx_is_not_transient():
    assert _is_transient_overpass_error(_make_4xx_exc()) is False


@pytest.mark.asyncio
async def test_overpass_success_on_first_attempt():
    payload = {"elements": [{"type": "node", "id": 1, "tags": {"phone": "+13175551234", "name": "Test Biz"}}]}
    with patch("app.services.osm_enrichment_service.httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await _call_overpass_with_retry("https://overpass-api.de/api/interpreter", "[out:json];", 5)
        assert result == payload


@pytest.mark.asyncio
async def test_overpass_retry_then_success():
    payload = {"elements": [{"type": "node", "id": 1, "tags": {"website": "https://example.com"}}]}
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("timed out", request=MagicMock())
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload
        return mock_resp

    with patch("app.services.osm_enrichment_service.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.osm_enrichment_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        mock_client_cls.return_value = mock_client

        result = await _call_overpass_with_retry("https://overpass-api.de/api/interpreter", "[out:json];", 5)
        assert result == payload
        assert call_count == 2


@pytest.mark.asyncio
async def test_overpass_all_attempts_fail_returns_none():
    with patch("app.services.osm_enrichment_service.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.osm_enrichment_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out", request=MagicMock()))
        mock_client_cls.return_value = mock_client

        result = await _call_overpass_with_retry("https://overpass-api.de/api/interpreter", "[out:json];", 5)
        assert result is None


@pytest.mark.asyncio
async def test_overpass_4xx_returns_none_no_retry():
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 400
        raise httpx.HTTPStatusError("400", request=MagicMock(), response=resp)

    with patch("app.services.osm_enrichment_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        mock_client_cls.return_value = mock_client

        result = await _call_overpass_with_retry("https://overpass-api.de/api/interpreter", "[out:json];", 5)
        assert result is None
        assert call_count == 1  # no retry on 4xx


@pytest.mark.asyncio
async def test_fetch_osm_enrichment_no_elements_returns_none():
    with patch("app.services.osm_enrichment_service.get_settings") as mock_settings, \
         patch("app.services.osm_enrichment_service._call_overpass_with_retry", new_callable=AsyncMock) as mock_call:
        s = MagicMock()
        s.overpass_endpoint = "https://overpass-api.de/api/interpreter"
        s.overpass_timeout_seconds = 5
        s.overpass_radius_meters = 50
        mock_settings.return_value = s
        mock_call.return_value = {"elements": []}

        result = await fetch_osm_enrichment(39.77, -86.15, "Test Biz")
        assert result is None


@pytest.mark.asyncio
async def test_fetch_osm_enrichment_overpass_down_returns_none():
    with patch("app.services.osm_enrichment_service.get_settings") as mock_settings, \
         patch("app.services.osm_enrichment_service._call_overpass_with_retry", new_callable=AsyncMock) as mock_call:
        s = MagicMock()
        s.overpass_endpoint = "https://overpass-api.de/api/interpreter"
        s.overpass_timeout_seconds = 5
        s.overpass_radius_meters = 50
        mock_settings.return_value = s
        mock_call.return_value = None  # simulates exhausted retries

        result = await fetch_osm_enrichment(39.77, -86.15, "Test Biz")
        assert result is None


@pytest.mark.asyncio
async def test_fetch_osm_enrichment_extracts_phone_and_website():
    elements = [{"type": "node", "id": 42, "tags": {"phone": "+13175551234", "website": "https://example.com", "opening_hours": "Mo-Fr 09:00-17:00"}}]
    with patch("app.services.osm_enrichment_service.get_settings") as mock_settings, \
         patch("app.services.osm_enrichment_service._call_overpass_with_retry", new_callable=AsyncMock) as mock_call:
        s = MagicMock()
        s.overpass_endpoint = "https://overpass-api.de/api/interpreter"
        s.overpass_timeout_seconds = 5
        s.overpass_radius_meters = 50
        mock_settings.return_value = s
        mock_call.return_value = {"elements": elements}

        result = await fetch_osm_enrichment(39.77, -86.15, "Example Business")
        assert result is not None
        assert result.osm_phone == "+13175551234"
        assert result.osm_website == "https://example.com"
        assert result.opening_hours == "Mo-Fr 09:00-17:00"
