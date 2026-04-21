from __future__ import annotations

import math
import re
from collections import defaultdict
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


VALID_SORT_BY = {
    "score", "blue_collar_score", "name", "distance",
    "validation_confidence", "follow_up_date", "last_contact",
    "owner_name", "saved_at",
}

GROUP_BY_CONFIGS: dict[str, dict] = {
    "insurance_class": {},
    "blue_collar":     {},
    "score_band":      {},
    "validation_state": {},
    "follow_up_urgency": {},
    "contact_status":  {},
    "owner_name_status": {},
}

SCORE_BAND_LABEL = {
    "high":   "High (≥70)",
    "medium": "Medium (40–69)",
    "low":    "Low (<40)",
}


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    if None in (lat1, lng1, lat2, lng2):
        return float("inf")
    r = 6_371_000.0
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lng2) - float(lng1))
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2) ** 2)
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_duplicate(candidate: dict, kept: dict) -> bool:
    name_a = _normalize_name(candidate.get("name"))
    name_b = _normalize_name(kept.get("name"))
    if not name_a or not name_b:
        return False
    if SequenceMatcher(a=name_a, b=name_b).ratio() < 0.85:
        return False
    if _haversine_m(candidate.get("lat"), candidate.get("lng"), kept.get("lat"), kept.get("lng")) > 100:
        return False
    phone_a = (candidate.get("phone") or "").strip()
    phone_b = (kept.get("phone") or "").strip()
    site_a = (candidate.get("website") or "").strip().lower().rstrip("/")
    site_b = (kept.get("website") or "").strip().lower().rstrip("/")
    return (bool(phone_a and phone_b and phone_a == phone_b)
            or bool(site_a and site_b and site_a == site_b))


def _dedupe_leads(rows: list[dict]) -> list[dict]:
    """O(n) dedup using phone/website indexes as fast-path candidate sets.

    Full fuzzy name + geo check only runs against rows that share a phone or
    website with the candidate — shrinks the comparison set from O(n) to O(k)
    where k is the number of rows with the same contact identifier (typically 1).
    """
    deduped: list[dict] = []
    phone_index: dict[str, list[dict]] = {}
    site_index: dict[str, list[dict]] = {}

    for row in rows:
        phone = (row.get("phone") or "").strip()
        site = (row.get("website") or "").strip().lower().rstrip("/")

        # Gather candidates that share phone or website — only these can match
        candidates: list[dict] = []
        if phone:
            candidates.extend(phone_index.get(phone, []))
        if site:
            for c in site_index.get(site, []):
                if c not in candidates:
                    candidates.append(c)

        if any(_is_duplicate(row, ex) for ex in candidates):
            continue

        deduped.append(row)
        if phone:
            phone_index.setdefault(phone, []).append(row)
        if site:
            site_index.setdefault(site, []).append(row)

    return deduped


def _score_band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _group_key(lead: dict, group_by: str) -> tuple[str, str]:
    """Return (key, label) for a lead under the given group_by mode."""
    if group_by == "insurance_class":
        cls = lead.get("insurance_class") or "Other Commercial"
        return cls, cls
    if group_by == "blue_collar":
        if lead.get("is_blue_collar"):
            return "blue_collar", "Blue Collar"
        return "other", "Other"
    if group_by == "score_band":
        band = _score_band(lead.get("final_score", 0))
        return band, SCORE_BAND_LABEL[band]
    if group_by == "validation_state":
        state = lead.get("validation_state") or "Unchecked"
        return state.lower().replace(" ", "_"), state
    if group_by == "owner_name_status":
        if lead.get("owner_name"):
            return "has_owner_name", "Has Owner Name"
        return "no_owner_name", "No Owner Name"
    return "unknown", "Unknown"


def _group_order(group_by: str) -> list[str]:
    if group_by == "score_band":
        return ["high", "medium", "low"]
    if group_by == "blue_collar":
        return ["blue_collar", "other"]
    if group_by == "validation_state":
        return ["validated", "mostly_valid", "needs_review", "low_confidence", "unchecked"]
    if group_by == "owner_name_status":
        return ["has_owner_name", "no_owner_name"]
    return []


def _apply_groups(leads: list[dict], group_by: str) -> list[dict]:
    """Return groups list (each is a dict with key/label/count/leads)."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    labels: dict[str, str] = {}
    for lead in leads:
        key, label = _group_key(lead, group_by)
        buckets[key].append(lead)
        labels[key] = label

    ordered_keys = _group_order(group_by)
    all_keys = ordered_keys + [k for k in buckets if k not in ordered_keys]

    groups = []
    for key in all_keys:
        if key not in buckets:
            continue
        group_leads = buckets[key]
        groups.append({
            "key": key,
            "label": labels[key],
            "count": len(group_leads),
            "leads": group_leads,
        })
    return groups


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
    priors: dict = {"segments": {}, "global": {"prior_save": 0.20, "prior_contact": 0.08, "sample_size": 0}}
    if compute_v2:
        priors = await load_feedback_priors(
            db, calibration_version=settings.scoring_feedback_calibration_version,
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

        route_candidate_rows.append({
            "route_id": route_id,
            "business_id": business_id,
            "distance_from_route_m": float(row["distance_from_route_m"]),
            "within_corridor": True,
        })
        lead_score_rows.append({
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
        })

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
    # Phase 10 params
    sort_by: str = "score",
    sort_dir: str = "desc",
    blue_collar: bool | None = None,
    has_owner_name: bool | None = None,
    has_employee_count: bool | None = None,
    employee_count_band: str | None = None,
    min_validation_confidence: float | None = None,
    validation_state: str | None = None,
    operating_status: str | None = None,
    score_band: str | None = None,
    group_by: str | None = None,
) -> tuple[list[dict], int, int, list[dict] | None]:
    """Return (leads, total, filtered, groups_or_None)."""
    if sort_by not in VALID_SORT_BY:
        raise ValueError(f"Invalid sort_by: {sort_by!r}. Must be one of {sorted(VALID_SORT_BY)}")

    score_version = resolve_score_version(requested_score_version)
    use_v2 = score_version == "v2"
    effective_final_expr = (
        func.coalesce(LeadScore.final_score_v2, LeadScore.final_score) if use_v2 else LeadScore.final_score
    )

    from app.models.business import Business

    base_q = (
        select(
            Business.id,
            Business.name,
            Business.insurance_class,
            Business.address_line1,
            Business.city,
            Business.phone,
            Business.website,
            Business.is_blue_collar,
            Business.owner_name,
            Business.owner_name_source,
            Business.owner_name_confidence,
            Business.employee_count_estimate,
            Business.employee_count_band,
            Business.employee_count_source,
            Business.employee_count_confidence,
            Business.operating_status,
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
        .join(
            RouteCandidate,
            (RouteCandidate.route_id == LeadScore.route_id)
            & (RouteCandidate.business_id == LeadScore.business_id),
        )
        .where(LeadScore.route_id == route_id)
    )

    filters = [effective_final_expr >= min_score]
    if has_phone is not None:
        filters.append(Business.has_phone.is_(has_phone))
    if has_website is not None:
        filters.append(Business.has_website.is_(has_website))
    if insurance_classes:
        filters.append(Business.insurance_class.in_(insurance_classes))
    if blue_collar is not None:
        filters.append(Business.is_blue_collar.is_(blue_collar))
    if has_owner_name is not None:
        if has_owner_name:
            filters.append(Business.owner_name.is_not(None))
        else:
            filters.append(Business.owner_name.is_(None))
    if operating_status:
        filters.append(Business.operating_status == operating_status)
    if has_employee_count is not None:
        if has_employee_count:
            filters.append(Business.employee_count_estimate.is_not(None))
        else:
            filters.append(Business.employee_count_estimate.is_(None))
    if employee_count_band:
        filters.append(Business.employee_count_band == employee_count_band)
    if score_band:
        band_filters = {"high": effective_final_expr >= 70, "medium": (effective_final_expr >= 40) & (effective_final_expr < 70), "low": effective_final_expr < 40}
        if score_band in band_filters:
            filters.append(band_filters[score_band])

    counts_q = (
        select(
            func.count().label("total"),
            func.count().filter(*filters).label("filtered"),
        )
        .select_from(Business)
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(RouteCandidate, (RouteCandidate.route_id == LeadScore.route_id) & (RouteCandidate.business_id == LeadScore.business_id))
        .where(LeadScore.route_id == route_id)
    )
    counts_row = (await db.execute(counts_q)).one()
    total = counts_row.total
    filtered = counts_row.filtered

    # Build ORDER BY
    asc_flag = sort_dir.lower() == "asc"
    if sort_by == "blue_collar_score":
        order_exprs = [
            Business.is_blue_collar.desc(),
            effective_final_expr.asc() if asc_flag else effective_final_expr.desc(),
        ]
    elif sort_by == "name":
        order_exprs = [Business.name.asc() if asc_flag else Business.name.desc()]
    elif sort_by == "distance":
        order_exprs = [RouteCandidate.distance_from_route_m.asc() if asc_flag else RouteCandidate.distance_from_route_m.desc()]
    elif sort_by == "owner_name":
        order_exprs = [Business.owner_name.asc().nulls_last() if asc_flag else Business.owner_name.desc().nulls_last()]
    else:
        order_exprs = [effective_final_expr.asc() if asc_flag else effective_final_expr.desc()]

    filtered_q = base_q.where(*filters).order_by(*order_exprs).limit(limit).offset(offset)
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

        lead_rows.append({
            "business_id": row["id"],
            "name": row["name"],
            "insurance_class": row["insurance_class"],
            "address": ", ".join([p for p in [row["address_line1"], row["city"]] if p]) or None,
            "phone": row["phone"],
            "website": row["website"],
            "is_blue_collar": bool(row["is_blue_collar"]),
            "owner_name": row["owner_name"],
            "owner_name_source": row["owner_name_source"],
            "owner_name_confidence": float(row["owner_name_confidence"]) if row["owner_name_confidence"] is not None else None,
            "employee_count_estimate": row["employee_count_estimate"],
            "employee_count_band": row["employee_count_band"],
            "employee_count_source": row["employee_count_source"],
            "employee_count_confidence": float(row["employee_count_confidence"]) if row["employee_count_confidence"] is not None else None,
            "operating_status": row["operating_status"],
            "final_score": (
                row["final_score_v2"] if use_v2 and row["final_score_v2"] is not None else row["final_score"]
            ),
            "fit_score": (row["fit_score_v2"] if use_v2 and row["fit_score_v2"] is not None else row["fit_score"]),
            "distance_score": (row["distance_score_v2"] if use_v2 and row["distance_score_v2"] is not None else row["distance_score"]),
            "actionability_score": (row["actionability_score_v2"] if use_v2 and row["actionability_score_v2"] is not None else row["actionability_score"]),
            "distance_from_route_m": float(row["distance_from_route_m"]),
            "explanation": explanation,
            "score_version": row["effective_score_version"] if use_v2 else "v1",
            "rank_reason_v2": rank_reason_v2 if use_v2 else None,
            "lat": float(row["lat"]) if row["lat"] is not None else None,
            "lng": float(row["lng"]) if row["lng"] is not None else None,
        })

    lead_rows = _dedupe_leads(lead_rows)

    groups = None
    if group_by and group_by in GROUP_BY_CONFIGS:
        groups = _apply_groups(lead_rows, group_by)

    return lead_rows, int(total or 0), int(filtered or 0), groups


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
