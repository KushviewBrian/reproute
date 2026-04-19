from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_PHONE_TAGS = ("phone", "contact:phone", "mobile", "contact:mobile")
_WEBSITE_TAGS = ("website", "contact:website", "url")
_OPERATOR_TAGS = ("operator", "owner")

# Retry policy for Overpass upstream calls.
# The public endpoint is unreliable under load; we attempt twice with a short
# delay before returning None (enrichment skipped, not a hard error).
# Only transient errors are retried; 4xx errors are terminal.
_OVERPASS_MAX_ATTEMPTS = 2
_OVERPASS_RETRY_DELAY_SECONDS = 1.0


@dataclass
class OsmEnrichmentResult:
    osm_phone: str | None
    osm_website: str | None
    opening_hours: str | None
    element_id: str | None
    osm_operator: str | None = None


def _extract_tags(elements: list[dict]) -> dict:
    """Return the tag dict from the first element that has tags."""
    for el in elements:
        tags = el.get("tags") or {}
        if tags:
            return tags
    return {}


def _clean_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip()
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7:
        return None
    return cleaned


def _clean_website(raw: str | None) -> str | None:
    if not raw:
        return None
    url = raw.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _build_query(lat: float, lng: float, name: str, radius: int) -> str:
    escaped = re.sub(r'([\\^$.|?*+()\[\]{}])', r'\\\1', name)
    return (
        f'[out:json][timeout:25];\n'
        f'(\n'
        f'  node(around:{radius},{lat},{lng})["name"~"{escaped}",i];\n'
        f'  way(around:{radius},{lat},{lng})["name"~"{escaped}",i];\n'
        f');\n'
        f'out body;\n'
    )


def _is_transient_overpass_error(exc: BaseException) -> bool:
    """Return True for errors that are safe to retry against Overpass."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


async def _call_overpass_with_retry(endpoint: str, query: str, timeout: int) -> dict | None:
    """
    POST to Overpass with up to _OVERPASS_MAX_ATTEMPTS attempts.

    - Transient errors (timeout, network, 5xx) are retried after _OVERPASS_RETRY_DELAY_SECONDS.
    - 4xx errors are terminal — returns None immediately (enrichment is best-effort).
    - If all attempts are exhausted, returns None so the caller records the
      attempted timestamp and continues without raising.
    """
    for attempt in range(1, _OVERPASS_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    endpoint,
                    content=query,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                return resp.json()
        except BaseException as exc:
            if not _is_transient_overpass_error(exc):
                logger.warning(
                    "overpass_terminal_error attempt=%d error=%r endpoint=%s",
                    attempt, exc, endpoint,
                )
                return None
            if attempt < _OVERPASS_MAX_ATTEMPTS:
                logger.warning(
                    "overpass_retry attempt=%d/%d error=%r endpoint=%s",
                    attempt, _OVERPASS_MAX_ATTEMPTS, exc, endpoint,
                )
                await asyncio.sleep(_OVERPASS_RETRY_DELAY_SECONDS)
            else:
                logger.warning(
                    "overpass_all_attempts_failed attempts=%d error=%r endpoint=%s"
                    " -- enrichment skipped for this business",
                    _OVERPASS_MAX_ATTEMPTS, exc, endpoint,
                )
    return None


async def fetch_osm_enrichment(lat: float, lng: float, name: str) -> OsmEnrichmentResult | None:
    """
    Query Overpass for OSM tags near (lat, lng) matching name.

    Returns OsmEnrichmentResult if useful tags are found, None otherwise.
    Never raises -- all failures are logged and swallowed so background
    enrichment tasks always complete cleanly.
    """
    settings = get_settings()
    query = _build_query(lat, lng, name, settings.overpass_radius_meters)

    data = await _call_overpass_with_retry(
        endpoint=settings.overpass_endpoint,
        query=query,
        timeout=settings.overpass_timeout_seconds,
    )

    if data is None:
        return None

    elements: list[dict] = data.get("elements") or []
    if not elements:
        return None

    tags = _extract_tags(elements)
    if not tags:
        return None

    phone = next((_clean_phone(tags.get(t)) for t in _PHONE_TAGS if tags.get(t)), None)
    website = next((_clean_website(tags.get(t)) for t in _WEBSITE_TAGS if tags.get(t)), None)
    hours = tags.get("opening_hours")
    osm_operator = next((tags.get(t, "").strip() or None for t in _OPERATOR_TAGS if tags.get(t, "").strip()), None)
    element_id = f"{elements[0].get('type', '?')}_{elements[0].get('id', '?')}"

    if not phone and not website and not hours and not osm_operator:
        return None

    return OsmEnrichmentResult(
        osm_phone=phone,
        osm_website=website,
        opening_hours=hours,
        osm_operator=osm_operator,
        element_id=element_id,
    )
