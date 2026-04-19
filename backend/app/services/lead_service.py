from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import case, delete, func, insert, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.lead_score import LeadScore
from app.models.route_candidate import RouteCandidate
from app.services.business_search_service import find_candidates
from app.services.scoring_feedback_service import load_feedback_priors
from app.services.scoring_service import score_candidate, score_candidate_v2


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
    settings = get_settings()
    compute_v2 = bool(settings.scoring_v2_shadow_enabled or settings.scoring_v2_enabled)
    priors = {"segments": {}, "global": {"prior_save": 0.20, "prior_contact": 0.08, "sample_size": 0}}
    if compute_v2:
        priors = await load_feedback_priors(
            db,
            calibration_version=settings.scoring_feedback_calibration_version,
        )

    for row in candidates:
        business_id = row["id"]
        scoring = score_candidate(row)
        scoring_v2 = None
        if compute_v2:
            scoring_v2 = score_candidate_v2(
                row,
                priors=priors,
                smoothing=settings.scoring_feedback_smoothing,
                min_segment_samples=settings.scoring_feedback_min_segment_samples,
                calibration_version=settings.scoring_feedback_calibration_version,
            )

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
                "fit_score_v2": scoring_v2["fit_score_v2"] if scoring_v2 else None,
                "distance_score_v2": scoring_v2["distance_score_v2"] if scoring_v2 else None,
                "actionability_score_v2": scoring_v2["actionability_score_v2"] if scoring_v2 else None,
                "feedback_score_v2": scoring_v2["feedback_score_v2"] if scoring_v2 else None,
                "final_score_v2": scoring_v2["final_score_v2"] if scoring_v2 else None,
                "calibration_version": scoring_v2["calibration_version"] if scoring_v2 else None,
                "score_explanation_json": scoring["explanation"],
                "score_explanation_v2_json": scoring_v2["explanation_v2"] if scoring_v2 else None,
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
    requested_score_version: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int, int]:
    score_version = resolve_score_version(requested_score_version)
    use_v2 = score_version == "v2"
    effective_final_expr = (
        func.coalesce(LeadScore.final_score_v2, LeadScore.final_score)
        if use_v2
        else LeadScore.final_score
    )

    base_query = (
        select(
            LeadScore.business_id,
            LeadScore.fit_score,
            LeadScore.distance_score,
            LeadScore.actionability_score,
            LeadScore.final_score,
            LeadScore.fit_score_v2,
            LeadScore.distance_score_v2,
            LeadScore.actionability_score_v2,
            LeadScore.feedback_score_v2,
            LeadScore.final_score_v2,
            LeadScore.calibration_version,
            LeadScore.score_explanation_json,
            LeadScore.score_explanation_v2_json,
            RouteCandidate.distance_from_route_m,
        )
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id)
    )

    from app.models.business import Business

    base_query = base_query.join(Business, Business.id == LeadScore.business_id)

    filters = [effective_final_expr >= min_score]
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
            LeadScore.fit_score_v2,
            LeadScore.distance_score_v2,
            LeadScore.actionability_score_v2,
            LeadScore.feedback_score_v2,
            LeadScore.final_score_v2,
            LeadScore.calibration_version,
            LeadScore.score_explanation_json,
            LeadScore.score_explanation_v2_json,
            RouteCandidate.distance_from_route_m,
            case(
                (LeadScore.final_score_v2.is_not(None), literal_column("'v2'")),
                else_=literal_column("'v1'"),
            ).label("effective_score_version"),
        )
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id, *filters)
        .order_by(effective_final_expr.desc())
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
        raw_explanation = (
            row["score_explanation_v2_json"]
            if use_v2 and row["score_explanation_v2_json"] is not None
            else row["score_explanation_json"]
        ) or {}
        explanation = {
            "fit": raw_explanation.get("fit") or "Fit unavailable",
            "distance": raw_explanation.get("distance") or "Distance unavailable",
            "actionability": raw_explanation.get("actionability") or "Actionability unavailable",
        }
        rank_reason_v2 = raw_explanation.get("rank_reason_v2")
        if not isinstance(rank_reason_v2, list):
            rank_reason_v2 = None

        lead_rows.append(
            {
                "business_id": row["id"],
                "name": row["name"],
                "insurance_class": row["insurance_class"],
                "address": ", ".join([p for p in [row["address_line1"], row["city"]] if p]) or None,
                "phone": row["phone"],
                "website": row["website"],
                "final_score": (
                    row["final_score_v2"] if use_v2 and row["final_score_v2"] is not None else row["final_score"]
                ),
                "fit_score": (
                    row["fit_score_v2"] if use_v2 and row["fit_score_v2"] is not None else row["fit_score"]
                ),
                "distance_score": (
                    row["distance_score_v2"] if use_v2 and row["distance_score_v2"] is not None else row["distance_score"]
                ),
                "actionability_score": (
                    row["actionability_score_v2"]
                    if use_v2 and row["actionability_score_v2"] is not None
                    else row["actionability_score"]
                ),
                "distance_from_route_m": float(row["distance_from_route_m"]),
                "explanation": explanation,
                "score_version": (
                    row["effective_score_version"] if use_v2 else "v1"
                ),
                "rank_reason_v2": rank_reason_v2 if use_v2 else None,
                "lat": float(row["lat"]) if row["lat"] is not None else None,
                "lng": float(row["lng"]) if row["lng"] is not None else None,
            }
        )

    lead_rows = _dedupe_leads(lead_rows)
    return lead_rows, int(total or 0), int(filtered or 0)


def resolve_score_version(requested_score_version: str | None) -> str:
    settings = get_settings()
    forced = settings.scoring_force_version.strip().lower()
    if forced in {"v1", "v2"}:
        if forced == "v2" and not settings.scoring_v2_enabled:
            return "v1"
        return forced

    requested = (requested_score_version or "").strip().lower()
    if requested == "v2":
        if settings.scoring_v2_enabled or settings.scoring_v2_shadow_enabled:
            return "v2"
        return "v1"
    if requested == "v1":
        return "v1"

    default = settings.scoring_default_version.strip().lower()
    if default == "v2" and settings.scoring_v2_enabled:
        return "v2"
    return "v1"
