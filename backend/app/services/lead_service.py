from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import delete, func, insert, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_score import LeadScore
from app.models.route_candidate import RouteCandidate
from app.services.business_search_service import find_candidates
from app.services.scoring_service import score_candidate


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _haversine_m(lat1: float | None, lng1: float | None, lat2: float | None, lng2: float | None) -> float:
    if None in (lat1, lng1, lat2, lng2):
        return float("inf")
    r = 6_371_000.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lng2) - float(lng1))
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2) ** 2)
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_duplicate(candidate: dict, kept: dict) -> bool:
    name_a = _normalize_name(candidate.get("name"))
    name_b = _normalize_name(kept.get("name"))
    if not name_a or not name_b:
        return False
    similarity = SequenceMatcher(a=name_a, b=name_b).ratio()
    if similarity < 0.85:
        return False
    distance_m = _haversine_m(candidate.get("lat"), candidate.get("lng"), kept.get("lat"), kept.get("lng"))
    if distance_m > 100:
        return False
    phone_a = (candidate.get("phone") or "").strip()
    phone_b = (kept.get("phone") or "").strip()
    site_a = (candidate.get("website") or "").strip().lower().rstrip("/")
    site_b = (kept.get("website") or "").strip().lower().rstrip("/")
    phone_match = bool(phone_a and phone_b and phone_a == phone_b)
    website_match = bool(site_a and site_b and site_a == site_b)
    return phone_match or website_match


def _dedupe_leads(rows: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    for row in rows:
        if any(_is_duplicate(row, existing) for existing in deduped):
            continue
        deduped.append(row)
    return deduped


async def refresh_route_candidates_and_scores(db: AsyncSession, route_id: UUID, corridor_width_meters: int) -> int:
    candidates = await find_candidates(db, route_id, corridor_width_meters)

    await db.execute(delete(RouteCandidate).where(RouteCandidate.route_id == route_id))
    await db.execute(delete(LeadScore).where(LeadScore.route_id == route_id))

    if not candidates:
        await db.commit()
        return 0

    route_candidate_rows = []
    lead_score_rows = []

    for row in candidates:
        business_id = row["id"]
        scoring = score_candidate(row)

        route_candidate_rows.append(
            {
                "route_id": route_id,
                "business_id": business_id,
                "distance_from_route_m": float(row["distance_from_route_m"]),
                "within_corridor": True,
            }
        )
        lead_score_rows.append(
            {
                "route_id": route_id,
                "business_id": business_id,
                "fit_score": scoring["fit_score"],
                "distance_score": scoring["distance_score"],
                "actionability_score": scoring["actionability_score"],
                "final_score": scoring["final_score"],
                "score_version": "v1",
                "score_explanation_json": scoring["explanation"],
            }
        )

    await db.execute(insert(RouteCandidate), route_candidate_rows)
    await db.execute(insert(LeadScore), lead_score_rows)
    await db.commit()
    return len(candidates)


async def fetch_leads(
    db: AsyncSession,
    route_id: UUID,
    min_score: int = 40,
    has_phone: bool | None = None,
    has_website: bool | None = None,
    insurance_classes: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int, int]:
    base_query = (
        select(
            LeadScore.business_id,
            LeadScore.fit_score,
            LeadScore.distance_score,
            LeadScore.actionability_score,
            LeadScore.final_score,
            LeadScore.score_explanation_json,
            RouteCandidate.distance_from_route_m,
        )
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id)
    )

    from app.models.business import Business

    base_query = base_query.join(Business, Business.id == LeadScore.business_id)

    filters = [LeadScore.final_score >= min_score]
    if has_phone is not None:
        filters.append(Business.has_phone.is_(has_phone))
    if has_website is not None:
        filters.append(Business.has_website.is_(has_website))
    if insurance_classes:
        filters.append(Business.insurance_class.in_(insurance_classes))

    total = await db.scalar(select(func.count()).select_from(LeadScore).where(LeadScore.route_id == route_id))

    filtered_q = (
        select(
            Business.id,
            Business.name,
            Business.insurance_class,
            Business.address_line1,
            Business.city,
            Business.phone,
            Business.website,
            literal_column("ST_Y(business.geom::geometry)").label("lat"),
            literal_column("ST_X(business.geom::geometry)").label("lng"),
            LeadScore.final_score,
            LeadScore.fit_score,
            LeadScore.distance_score,
            LeadScore.actionability_score,
            LeadScore.score_explanation_json,
            RouteCandidate.distance_from_route_m,
        )
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id, *filters)
        .order_by(LeadScore.final_score.desc())
        .limit(limit)
        .offset(offset)
    )

    count_filtered_q = (
        select(func.count())
        .select_from(Business)
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id, *filters)
    )

    filtered = await db.scalar(count_filtered_q)
    rows = (await db.execute(filtered_q)).mappings().all()

    lead_rows: list[dict] = []
    for row in rows:
        lead_rows.append(
            {
                "business_id": row["id"],
                "name": row["name"],
                "insurance_class": row["insurance_class"],
                "address": ", ".join([p for p in [row["address_line1"], row["city"]] if p]) or None,
                "phone": row["phone"],
                "website": row["website"],
                "final_score": row["final_score"],
                "fit_score": row["fit_score"],
                "distance_score": row["distance_score"],
                "actionability_score": row["actionability_score"],
                "distance_from_route_m": float(row["distance_from_route_m"]),
                "explanation": row["score_explanation_json"],
                "lat": float(row["lat"]) if row["lat"] is not None else None,
                "lng": float(row["lng"]) if row["lng"] is not None else None,
            }
        )

    lead_rows = _dedupe_leads(lead_rows)
    return lead_rows, int(total or 0), int(filtered or 0)
