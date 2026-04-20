from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import _get_engine
from app.models.business import Business
from app.models.lead_score import LeadScore
from app.models.route_candidate import RouteCandidate
from app.services.contact_intelligence import promote_owner_name
from app.services.osm_enrichment_service import OsmEnrichmentResult, fetch_osm_enrichment
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------------


async def reserve_enrichment_caps(user_id: UUID | None) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    day_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")
    keys = [
        (f"enrich:global:day:{day_key}", settings.enrichment_daily_cap, 2 * 24 * 60 * 60),
        (f"enrich:global:month:{month_key}", settings.enrichment_monthly_cap, 40 * 24 * 60 * 60),
    ]
    if user_id is not None:
        keys.append((
            f"enrich:user:{user_id}:day:{day_key}",
            settings.enrichment_per_user_daily_cap,
            2 * 24 * 60 * 60,
        ))
    for key, limit, ttl in keys:
        value = await redis_client.incr(key)
        if value is None:
            # Redis unavailable — fail open, log critical in production
            if get_settings().is_production():
                logger.critical("enrichment_rate_redis_unavailable key=%s — cap bypassed in production", key)
            return
        if value == 1:
            await redis_client.expire(key, ttl)
        if int(value) > int(limit):
            raise PermissionError("Enrichment cap exceeded")


# ---------------------------------------------------------------------------
# Freshness check
# ---------------------------------------------------------------------------

def _is_fresh(business: Business) -> bool:
    if business.osm_enriched_at is None:
        return False
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().enrichment_freshness_days)
    enriched = business.osm_enriched_at
    if enriched.tzinfo is None:
        enriched = enriched.replace(tzinfo=UTC)
    return enriched >= cutoff


# ---------------------------------------------------------------------------
# Merge OSM result into Business row
# ---------------------------------------------------------------------------

async def apply_enrichment(db: AsyncSession, business: Business, result: OsmEnrichmentResult) -> None:
    """Write OSM values into osm_* columns; promote to primary only when primary is null."""
    business.osm_enriched_at = datetime.now(UTC)
    business.osm_phone = result.osm_phone
    business.osm_website = result.osm_website

    phone_promoted = bool(result.osm_phone and not business.phone)
    website_promoted = bool(result.osm_website and not business.website)

    if phone_promoted:
        business.phone = result.osm_phone
        business.has_phone = True
    if website_promoted:
        business.website = result.osm_website
        business.has_website = True

    # Write owner_name from OSM operator tag when no higher-confidence source exists
    operator = getattr(result, "osm_operator", None)
    if operator:
        await promote_owner_name(
            db,
            business,
            owner_name=operator,
            source="osm_operator",
            evidence_json={"source": "osm", "element_id": result.element_id},
        )

    await db.commit()

    if phone_promoted or website_promoted:
        logger.info(
            "osm_enrichment_applied business_id=%s element_id=%s phone_promoted=%s website_promoted=%s",
            business.id,
            result.element_id,
            phone_promoted,
            website_promoted,
        )
    else:
        logger.debug("osm_enrichment_stored business_id=%s element_id=%s", business.id, result.element_id)


# ---------------------------------------------------------------------------
# Core enrichment entry point
# ---------------------------------------------------------------------------

async def enrich_business(
    db: AsyncSession,
    business_id: UUID,
    user_id: UUID | None = None,
    force: bool = False,
) -> bool:
    """
    Fetch a Business row, run OSM enrichment, and persist results.
    Returns True if enrichment ran, False if skipped (fresh / no data / not found).
    Raises PermissionError if quota is exhausted.

    Intentionally reads needed fields then closes the DB transaction before
    making the Overpass HTTP call, so no connection is held across network I/O.
    """
    business = await db.get(Business, business_id)
    if business is None:
        return False

    if not force and _is_fresh(business):
        return False

    lat_lng = (
        await db.execute(
            select(
                literal_column("ST_Y(business.geom::geometry)").label("lat"),
                literal_column("ST_X(business.geom::geometry)").label("lng"),
            ).where(Business.id == business_id)
        )
    ).first()

    if lat_lng is None or lat_lng.lat is None or lat_lng.lng is None:
        return False

    # Snapshot what we need, then release the connection before the HTTP call.
    lat = float(lat_lng.lat)
    lng = float(lat_lng.lng)
    name = business.name
    await db.rollback()  # release the connection back to the pool cleanly

    await reserve_enrichment_caps(user_id)

    result = await fetch_osm_enrichment(lat=lat, lng=lng, name=name)

    # Re-fetch the row for the write — connection was released above
    business = await db.get(Business, business_id)
    if business is None:
        return False

    if result is None:
        business.osm_enriched_at = datetime.now(UTC)
        await db.commit()
        return False

    await apply_enrichment(db, business, result)
    return True


# ---------------------------------------------------------------------------
# Background enrichment for route leads (top-N by score, missing contact info)
# ---------------------------------------------------------------------------

async def enrich_route_top_leads(route_id: UUID, limit: int = 20) -> None:
    """
    Enrich the top `limit` route leads that are missing phone or website.
    Uses a short-lived session only for the candidate query, then opens a
    fresh session per business so no connection is held across Overpass HTTP calls.
    All errors are swallowed.
    """
    _, SessionLocal = _get_engine()
    try:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Business.id)
                    .join(LeadScore, LeadScore.business_id == Business.id)
                    .join(
                        RouteCandidate,
                        (RouteCandidate.route_id == LeadScore.route_id)
                        & (RouteCandidate.business_id == LeadScore.business_id),
                    )
                    .where(
                        LeadScore.route_id == route_id,
                        (Business.has_phone.is_(False)) | (Business.has_website.is_(False)),
                    )
                    .order_by(LeadScore.final_score.desc())
                    .limit(limit)
                )
            ).scalars().all()
    except Exception as exc:
        logger.warning("osm_enrich_route_query_error route_id=%s error=%r", route_id, exc)
        return

    for business_id in rows:
        try:
            async with SessionLocal() as db:
                await enrich_business(db, business_id, user_id=None, force=False)
        except PermissionError:
            logger.info("osm_enrich_route_cap_reached route_id=%s", route_id)
            break
        except Exception as exc:
            logger.warning("osm_enrich_route_lead_error business_id=%s error=%r", business_id, exc)


# ---------------------------------------------------------------------------
# Background enrichment on lead save
# ---------------------------------------------------------------------------

async def enrich_saved_lead(business_id: UUID, user_id: UUID) -> None:
    """
    Enrich a single saved lead. Opens its own DB session — safe to call as a
    FastAPI BackgroundTask. All errors are swallowed.
    """
    _, SessionLocal = _get_engine()
    try:
        async with SessionLocal() as db:
            await enrich_business(db, business_id, user_id=user_id, force=False)
    except PermissionError:
        logger.info("osm_enrich_save_cap_reached user_id=%s business_id=%s", user_id, business_id)
    except Exception as exc:
        logger.warning("osm_enrich_save_error user_id=%s business_id=%s error=%r", user_id, business_id, exc)
