from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.business import Business
from app.models.lead_score import LeadScore
from app.models.note import Note
from app.models.route import Route
from app.models.route_candidate import RouteCandidate
from app.models.saved_lead import SavedLead
from app.models.user import User
from app.schemas.saved_lead import (
    CreateSavedLeadRequest,
    SavedLeadGroup,
    SavedLeadItem,
    SavedLeadsTodayResponse,
    TodayRecentRoute,
    UpdateSavedLeadRequest,
)
from app.services.enrichment_service import enrich_saved_lead
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter()

VALID_SAVED_SORT_BY = {
    "score", "blue_collar_score", "name", "distance",
    "validation_confidence", "follow_up_date", "last_contact",
    "owner_name", "saved_at",
}

GROUP_BY_SAVED_CONFIGS = {
    "insurance_class", "blue_collar", "score_band",
    "validation_state", "follow_up_urgency", "contact_status", "owner_name_status",
}


def _format_route_label(origin_label, destination_label) -> str | None:
    if not origin_label and not destination_label:
        return None
    return f"{origin_label or 'Unknown start'} → {destination_label or 'Unknown destination'}"


def _to_saved_lead_item(row, notes_by_business: dict) -> SavedLeadItem:
    note = notes_by_business.get(row.SavedLead.business_id) or (None, None)
    return SavedLeadItem(
        id=row.SavedLead.id,
        user_id=row.SavedLead.user_id,
        route_id=row.SavedLead.route_id,
        business_id=row.SavedLead.business_id,
        status=row.SavedLead.status,
        priority=row.SavedLead.priority,
        next_follow_up_at=row.SavedLead.next_follow_up_at,
        last_contact_attempt_at=row.SavedLead.last_contact_attempt_at,
        business_name=row.name,
        phone=row.phone,
        website=row.website,
        address=", ".join(p for p in [row.address_line1, row.city, row.state] if p) or None,
        route_label=_format_route_label(row.origin_label, row.destination_label),
        final_score=int(row.final_score) if row.final_score is not None else None,
        latest_note_text=note[0],
        latest_note_created_at=note[1],
        # Phase 10
        is_blue_collar=bool(row.is_blue_collar) if hasattr(row, "is_blue_collar") else False,
        owner_name=row.owner_name if hasattr(row, "owner_name") else None,
        owner_name_source=row.owner_name_source if hasattr(row, "owner_name_source") else None,
        owner_name_confidence=float(row.owner_name_confidence) if (hasattr(row, "owner_name_confidence") and row.owner_name_confidence is not None) else None,
        insurance_class=row.insurance_class if hasattr(row, "insurance_class") else None,
        operating_status=row.operating_status if hasattr(row, "operating_status") else None,
    )


async def _hydrate_saved_lead_items(db, user_id, rows) -> list[SavedLeadItem]:
    business_ids = [r.SavedLead.business_id for r in rows]
    notes_by_business: dict = {}
    if business_ids:
        note_rows = (
            await db.execute(
                select(Note.business_id, Note.note_text, Note.created_at)
                .where(Note.user_id == user_id, Note.business_id.in_(business_ids))
                .order_by(Note.business_id, Note.created_at.desc())
            )
        ).all()
        for business_id, note_text, created_at in note_rows:
            if business_id not in notes_by_business:
                notes_by_business[business_id] = (note_text, created_at)
    return [_to_saved_lead_item(row, notes_by_business) for row in rows]


def _saved_leads_base_query(user_id: UUID):
    return (
        select(
            SavedLead,
            Business.name,
            Business.phone,
            Business.website,
            Business.address_line1,
            Business.city,
            Business.state,
            Business.insurance_class,
            Business.operating_status,
            Business.is_blue_collar,
            Business.owner_name,
            Business.owner_name_source,
            Business.owner_name_confidence,
            Route.origin_label,
            Route.destination_label,
            LeadScore.final_score,
        )
        .join(Business, Business.id == SavedLead.business_id, isouter=True)
        .join(Route, Route.id == SavedLead.route_id, isouter=True)
        .join(
            LeadScore,
            (LeadScore.route_id == SavedLead.route_id) & (LeadScore.business_id == SavedLead.business_id),
            isouter=True,
        )
        .where(SavedLead.user_id == user_id)
    )


def _apply_saved_sort(q, sort_by: str, sort_dir: str):
    asc = sort_dir.lower() == "asc"
    if sort_by == "blue_collar_score":
        return q.order_by(Business.is_blue_collar.desc(), LeadScore.final_score.desc().nulls_last())
    if sort_by == "name":
        return q.order_by(Business.name.asc() if asc else Business.name.desc())
    if sort_by == "owner_name":
        return q.order_by(Business.owner_name.asc().nulls_last() if asc else Business.owner_name.desc().nulls_last())
    if sort_by == "follow_up_date":
        return q.order_by(SavedLead.next_follow_up_at.asc().nulls_last())
    if sort_by == "last_contact":
        return q.order_by(SavedLead.last_contact_attempt_at.desc().nulls_last())
    if sort_by == "saved_at":
        return q.order_by(SavedLead.created_at.asc() if asc else SavedLead.created_at.desc())
    if sort_by == "score":
        return q.order_by(LeadScore.final_score.desc().nulls_last() if not asc else LeadScore.final_score.asc().nulls_last())
    # default: follow_up urgency then created_at
    return q.order_by(SavedLead.next_follow_up_at.asc().nulls_last(), SavedLead.created_at.desc())


def _saved_group_key(item: SavedLeadItem, group_by: str, now: datetime) -> tuple[str, str]:
    if group_by == "insurance_class":
        cls = item.insurance_class or "Other Commercial"
        return cls, cls
    if group_by == "blue_collar":
        return ("blue_collar", "Blue Collar") if item.is_blue_collar else ("other", "Other")
    if group_by == "score_band":
        s = item.final_score or 0
        if s >= 70: return "high", "High (≥70)"
        if s >= 40: return "medium", "Medium (40–69)"
        return "low", "Low (<40)"
    if group_by == "contact_status":
        if item.status in ("called", "visited"): return "contacted", "Contacted"
        if item.status == "not_interested": return "not_interested", "Not Interested"
        return "saved_untouched", "Saved / Untouched"
    if group_by == "owner_name_status":
        return ("has_owner_name", "Has Owner Name") if item.owner_name else ("no_owner_name", "No Owner Name")
    if group_by == "follow_up_urgency":
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_tomorrow = start_of_today + timedelta(days=1)
        fu = item.next_follow_up_at
        if fu is None:
            return "no_date", "No Date"
        if fu.tzinfo is None:
            fu = fu.replace(tzinfo=timezone.utc)
        if fu < start_of_today:
            return "overdue", "Overdue"
        if fu < start_of_tomorrow:
            return "due_today", "Due Today"
        return "upcoming", "Upcoming"
    return "unknown", "Unknown"


_SAVED_GROUP_ORDER = {
    "follow_up_urgency": ["overdue", "due_today", "upcoming", "no_date"],
    "contact_status": ["contacted", "saved_untouched", "not_interested"],
    "score_band": ["high", "medium", "low"],
    "blue_collar": ["blue_collar", "other"],
    "owner_name_status": ["has_owner_name", "no_owner_name"],
}


def _apply_saved_groups(items: list[SavedLeadItem], group_by: str) -> list[dict]:
    from collections import defaultdict
    now = datetime.now(timezone.utc)
    buckets: dict[str, list] = defaultdict(list)
    labels: dict[str, str] = {}
    for item in items:
        key, label = _saved_group_key(item, group_by, now)
        buckets[key].append(item)
        labels[key] = label
    ordered = _SAVED_GROUP_ORDER.get(group_by, [])
    all_keys = ordered + [k for k in buckets if k not in ordered]
    groups = []
    for key in all_keys:
        if key not in buckets:
            continue
        groups.append({
            "key": key,
            "label": labels[key],
            "count": len(buckets[key]),
            "leads": buckets[key],
        })
    return groups


@router.post("", response_model=SavedLeadItem)
async def create_saved_lead(
    payload: CreateSavedLeadRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    existing = (
        await db.execute(
            select(SavedLead).where(SavedLead.user_id == user.id, SavedLead.business_id == payload.business_id)
        )
    ).scalar_one_or_none()
    if existing:
        return SavedLeadItem(
            id=existing.id,
            user_id=existing.user_id,
            route_id=existing.route_id,
            business_id=existing.business_id,
            status=existing.status,
            priority=existing.priority,
            next_follow_up_at=existing.next_follow_up_at,
            last_contact_attempt_at=existing.last_contact_attempt_at,
        )

    item = SavedLead(user_id=user.id, business_id=payload.business_id, route_id=payload.route_id)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(
                select(SavedLead).where(SavedLead.user_id == user.id, SavedLead.business_id == payload.business_id)
            )
        ).scalar_one_or_none()
        if not existing:
            raise
        item = existing

    background_tasks.add_task(enrich_saved_lead, item.business_id, user.id)
    return SavedLeadItem(
        id=item.id, user_id=item.user_id, route_id=item.route_id,
        business_id=item.business_id, status=item.status, priority=item.priority,
        next_follow_up_at=item.next_follow_up_at, last_contact_attempt_at=item.last_contact_attempt_at,
    )


@router.get("", response_model=list[SavedLeadItem])
async def list_saved_leads(
    status: str | None = Query(default=None),
    due_before: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    # Phase 10
    sort_by: str = Query(default="follow_up_date"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    blue_collar: bool | None = None,
    has_owner_name: bool | None = None,
    operating_status: str | None = None,
    score_band: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    has_notes: bool | None = None,
    saved_after: datetime | None = Query(default=None),
    saved_before: datetime | None = Query(default=None),
    overdue_only: bool | None = None,
    untouched_only: bool | None = None,
    group_by: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedLeadItem]:
    sort_by = sort_by if isinstance(sort_by, str) else "follow_up_date"
    if sort_by not in VALID_SAVED_SORT_BY:
        raise HTTPException(status_code=422, detail=f"Invalid sort_by '{sort_by}'. Must be one of: {sorted(VALID_SAVED_SORT_BY)}")

    q = _saved_leads_base_query(user.id)

    if status:
        q = q.where(SavedLead.status == status)
    if due_before:
        q = q.where(SavedLead.next_follow_up_at.is_not(None), SavedLead.next_follow_up_at <= due_before)
    if blue_collar is not None:
        q = q.where(Business.is_blue_collar.is_(blue_collar))
    if has_owner_name is not None:
        q = q.where(Business.owner_name.is_not(None) if has_owner_name else Business.owner_name.is_(None))
    if operating_status:
        q = q.where(Business.operating_status == operating_status)
    if score_band:
        if score_band == "high":
            q = q.where(LeadScore.final_score >= 70)
        elif score_band == "medium":
            q = q.where(LeadScore.final_score >= 40, LeadScore.final_score < 70)
        else:
            q = q.where(LeadScore.final_score < 40)
    if has_notes is not None:
        note_sub = select(Note.business_id).where(Note.user_id == user.id).distinct()
        if has_notes:
            q = q.where(SavedLead.business_id.in_(note_sub))
        else:
            q = q.where(~SavedLead.business_id.in_(note_sub))
    if saved_after:
        q = q.where(SavedLead.created_at >= saved_after)
    if saved_before:
        q = q.where(SavedLead.created_at <= saved_before)
    if overdue_only:
        now = datetime.now(timezone.utc)
        q = q.where(
            SavedLead.next_follow_up_at.is_not(None),
            SavedLead.next_follow_up_at < now,
            SavedLead.status.notin_(["called", "visited", "not_interested"]),
        )
    if untouched_only:
        q = q.where(SavedLead.last_contact_attempt_at.is_(None))

    q = _apply_saved_sort(q, sort_by, sort_dir).limit(limit).offset(offset)
    rows = (await db.execute(q)).all()
    return await _hydrate_saved_lead_items(db, user.id, rows)


@router.get("/today", response_model=SavedLeadsTodayResponse)
async def get_saved_leads_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadsTodayResponse:
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_tomorrow = start_of_today + timedelta(days=1)

    base = _saved_leads_base_query(user.id)
    unresolved = SavedLead.status.notin_(["visited", "not_interested"])

    overdue_rows = (await db.execute(
        base.where(unresolved, SavedLead.next_follow_up_at.is_not(None), SavedLead.next_follow_up_at < start_of_today)
        .order_by(SavedLead.next_follow_up_at.asc()).limit(25)
    )).all()

    due_today_rows = (await db.execute(
        base.where(unresolved, SavedLead.next_follow_up_at.is_not(None),
                   SavedLead.next_follow_up_at >= start_of_today, SavedLead.next_follow_up_at < start_of_tomorrow)
        .order_by(SavedLead.next_follow_up_at.asc()).limit(25)
    )).all()

    untouched_rows = (await db.execute(
        base.where(SavedLead.status == "saved", SavedLead.last_contact_attempt_at.is_(None), LeadScore.final_score >= 70)
        .order_by(LeadScore.final_score.desc(), SavedLead.created_at.asc()).limit(5)
    )).all()

    # Phase 10: Blue Collar Today - overdue/due today filtered to is_blue_collar
    blue_collar_today_rows = (await db.execute(
        base.where(
            unresolved,
            Business.is_blue_collar.is_(True),
            SavedLead.next_follow_up_at.is_not(None),
            SavedLead.next_follow_up_at < start_of_tomorrow,
        ).order_by(SavedLead.next_follow_up_at.asc()).limit(5)
    )).all()

    # Phase 10: Has Owner Name - top unsaved high-score leads with owner_name set
    has_owner_rows = (await db.execute(
        base.where(
            SavedLead.status == "saved",
            Business.owner_name.is_not(None),
            LeadScore.final_score >= 50,
        ).order_by(LeadScore.final_score.desc()).limit(5)
    )).all()

    latest_route = (
        await db.execute(select(Route).where(Route.user_id == user.id).order_by(Route.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    recent_route = None
    if latest_route:
        unsaved_count = await db.scalar(
            select(func.count()).where(
                RouteCandidate.route_id == latest_route.id,
                ~exists(select(SavedLead.id).where(
                    and_(SavedLead.user_id == user.id, SavedLead.business_id == RouteCandidate.business_id)
                )),
            )
        )
        recent_route = TodayRecentRoute(
            route_id=latest_route.id,
            label=_format_route_label(latest_route.origin_label, latest_route.destination_label) or "Recent route",
            unsaved_lead_count=int(unsaved_count or 0),
        )

    return SavedLeadsTodayResponse(
        overdue=await _hydrate_saved_lead_items(db, user.id, overdue_rows),
        due_today=await _hydrate_saved_lead_items(db, user.id, due_today_rows),
        high_priority_untouched=await _hydrate_saved_lead_items(db, user.id, untouched_rows),
        recent_route=recent_route,
        blue_collar_today=await _hydrate_saved_lead_items(db, user.id, blue_collar_today_rows),
        has_owner_name=await _hydrate_saved_lead_items(db, user.id, has_owner_rows),
    )


@router.patch("/{saved_lead_id}", response_model=SavedLeadItem)
async def update_saved_lead(
    saved_lead_id: UUID,
    payload: UpdateSavedLeadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    item = (await db.execute(
        select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Saved lead not found")

    if payload.status is not None:
        item.status = payload.status
    if payload.priority is not None:
        item.priority = payload.priority
    if "next_follow_up_at" in payload.model_fields_set:
        item.next_follow_up_at = payload.next_follow_up_at
    if "last_contact_attempt_at" in payload.model_fields_set:
        item.last_contact_attempt_at = payload.last_contact_attempt_at

    # Phase 10: manual owner_name entry — source = manual, confidence = 1.0, never overwritten
    if "owner_name" in payload.model_fields_set and payload.owner_name is not None:
        business = await db.get(Business, item.business_id)
        if business:
            from app.services.enrichment_service import _write_owner_name
            # Force manual write by temporarily clearing source so it wins
            business.owner_name_source = None
            _write_owner_name(business, payload.owner_name, source="manual", confidence=1.0)

    await db.commit()
    return SavedLeadItem(
        id=item.id, user_id=item.user_id, route_id=item.route_id,
        business_id=item.business_id, status=item.status, priority=item.priority,
        next_follow_up_at=item.next_follow_up_at, last_contact_attempt_at=item.last_contact_attempt_at,
    )


@router.delete("/{saved_lead_id}")
async def delete_saved_lead(
    saved_lead_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    item = (await db.execute(
        select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Saved lead not found")
    await db.delete(item)
    await db.commit()
    return {"message": "deleted"}
