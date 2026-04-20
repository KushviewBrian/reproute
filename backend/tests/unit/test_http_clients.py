from __future__ import annotations

import pytest

import app.utils.http_clients as http_clients


@pytest.mark.asyncio
async def test_http_clients_init_and_close_cycle() -> None:
    await http_clients.close_http_clients()
    await http_clients.init_http_clients()
    assert http_clients.ors_client is not None
    assert http_clients.geocode_client is not None
    assert http_clients.overpass_client is not None
    assert http_clients.validation_client is not None
    await http_clients.close_http_clients()
    assert http_clients.ors_client is None
    assert http_clients.geocode_client is None
    assert http_clients.overpass_client is None
    assert http_clients.validation_client is None


@pytest.mark.asyncio
async def test_http_client_getters_reuse_singletons() -> None:
    await http_clients.close_http_clients()
    ors_a = http_clients.get_ors_client()
    ors_b = http_clients.get_ors_client()
    geo_a = http_clients.get_geocode_client()
    geo_b = http_clients.get_geocode_client()
    over_a = http_clients.get_overpass_client()
    over_b = http_clients.get_overpass_client()
    val_a = http_clients.get_validation_client()
    val_b = http_clients.get_validation_client()
    assert ors_a is ors_b
    assert geo_a is geo_b
    assert over_a is over_b
    assert val_a is val_b
    await http_clients.close_http_clients()
