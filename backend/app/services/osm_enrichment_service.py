from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_PHONE_TAGS = ("phone", "contact:phone", "mobile", "contact:mobile")
_WEBSITE_TAGS = ("website", "contact:website", "url")
_HOURS_TAGS = ("opening_hours",)


@dataclass
class OsmEnrichmentResult:
    osm_phone: str | None
    osm_website: str | None
    opening_hours: str | None
    element_id: str | None


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
    # Keep only if it has enough digits to be a real phone number
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
    # Escape name for Overpass regex — keep it simple, just escape special chars
    escaped = re.sub(r'([\\^$.|?*+()\[\]{}])', r'\\\1', name)
    return (
        f'[out:json][timeout:25];\n'
        f'(\n'
        f'  node(around:{radius},{lat},{lng})["name"~"{escaped}",i];\n'
        f'  way(around:{radius},{lat},{lng})["name"~"{escaped}",i];\n'
        f');\n'
        f'out body;\n'
    )


async def fetch_osm_enrichment(
    lat: float,
    lng: float,
    name: str,
) -> OsmEnrichmentResult | None:
    settings = get_settings()
    query = _build_query(lat, lng, name, settings.overpass_radius_meters)

    try:
        async with httpx.AsyncClient(timeout=settings.overpass_timeout_seconds) as client:
            resp = await client.post(
                settings.overpass_endpoint,
                content=query,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("osm_enrichment_timeout lat=%s lng=%s name=%r", lat, lng, name)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("osm_enrichment_http_error status=%s lat=%s lng=%s", exc.response.status_code, lat, lng)
        return None
    except Exception as exc:
        logger.warning("osm_enrichment_error lat=%s lng=%s error=%r", lat, lng, exc)
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
    element_id = f"{elements[0].get('type','?')}/{elements[0].get('id','?')}"

    if not phone and not website and not hours:
        return None

    return OsmEnrichmentResult(
        osm_phone=phone,
        osm_website=website,
        opening_hours=hours,
        element_id=element_id,
    )
