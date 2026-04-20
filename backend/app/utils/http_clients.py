from __future__ import annotations

import httpx

from app.core.config import get_settings

ors_client: httpx.AsyncClient | None = None
geocode_client: httpx.AsyncClient | None = None
overpass_client: httpx.AsyncClient | None = None


async def init_http_clients() -> None:
    """Initialize shared upstream HTTP clients once per app lifecycle."""
    global ors_client, geocode_client, overpass_client
    settings = get_settings()
    if ors_client is None:
        ors_client = httpx.AsyncClient(timeout=10)
    if geocode_client is None:
        geocode_client = httpx.AsyncClient(timeout=settings.geocode_timeout_seconds)
    if overpass_client is None:
        overpass_client = httpx.AsyncClient(timeout=settings.overpass_timeout_seconds)


async def close_http_clients() -> None:
    """Close shared upstream HTTP clients on shutdown."""
    global ors_client, geocode_client, overpass_client
    for client in (ors_client, geocode_client, overpass_client):
        if client is not None:
            await client.aclose()
    ors_client = None
    geocode_client = None
    overpass_client = None


def get_ors_client() -> httpx.AsyncClient:
    global ors_client
    if ors_client is None:
        ors_client = httpx.AsyncClient(timeout=10)
    return ors_client


def get_geocode_client() -> httpx.AsyncClient:
    global geocode_client
    if geocode_client is None:
        settings = get_settings()
        geocode_client = httpx.AsyncClient(timeout=settings.geocode_timeout_seconds)
    return geocode_client


def get_overpass_client() -> httpx.AsyncClient:
    global overpass_client
    if overpass_client is None:
        settings = get_settings()
        overpass_client = httpx.AsyncClient(timeout=settings.overpass_timeout_seconds)
    return overpass_client

