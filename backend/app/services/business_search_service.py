from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


CANDIDATE_QUERY = text(
    """
    SELECT
      b.id,
      b.name,
      b.insurance_class,
      b.address_line1,
      b.city,
      b.phone,
      b.website,
      b.confidence_score,
      b.last_seen_at,
      b.has_phone,
      b.has_website,
      b.has_address,
      lv.validation_confidence,
      lv.validation_last_checked_at,
      ST_Y(b.geom::geometry) AS lat,
      ST_X(b.geom::geometry) AS lng,
      ST_Distance(b.geom::geography, r.route_geom::geography) AS distance_from_route_m
    FROM business b
    LEFT JOIN (
      SELECT
        business_id,
        AVG(confidence) AS validation_confidence,
        MAX(last_checked_at) AS validation_last_checked_at
      FROM lead_field_validation
      GROUP BY business_id
    ) lv ON lv.business_id = b.id
    CROSS JOIN route r
    WHERE r.id = :route_id
      AND COALESCE(b.insurance_class, '') != 'Exclude'
      AND ST_DWithin(b.geom::geography, r.route_geom::geography, :corridor_width_meters)
    ORDER BY distance_from_route_m ASC
    """
)


async def find_candidates(db: AsyncSession, route_id: UUID, corridor_width_meters: int) -> list[dict]:
    result = await db.execute(
        CANDIDATE_QUERY,
        {"route_id": str(route_id), "corridor_width_meters": corridor_width_meters},
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]
