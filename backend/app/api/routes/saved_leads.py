from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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
    SavedLeadItem,
    SavedLeadsTodayResponse,
    TodayRecentRoute,
    UpdateSavedLeadRequest,
)
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter()


def _format_route_label(origin_label: str | None, destination_label: str | None) -> str | None:
    if not origin_label and not destination_label:
        return None
    return f"{origin_label or 'Unknown start'} → {destination_label or 'Unknown destination'}"


def _to_saved_lead_item(row, notes_by_business: dict[UUID, tuple[str, object]]) -> SavedLeadItem:
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
    )


async def _hydrate_saved_lead_items(
    db: AsyncSession,
    user_id: UUID,
    rows,
) -> list[SavedLeadItem]:
    business_ids = [r.SavedLead.business_id for r in rows]
    notes_by_business: dict[UUID, tuple[str, object]] = {}
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


@router.post("", response_model=SavedLeadItem)
async def create_saved_lead(
    payload: CreateSavedLeadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    existing = (
        await db.execute(
            select(SavedLead).where(
                SavedLead.user_id == user.id,
                SavedLead.business_id == payload.business_id,
            )
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
                select(SavedLead).where(
                    SavedLead.user_id == user.id,
                    SavedLead.business_id == payload.business_id,
                )
            )
        ).scalar_one_or_none()
        if not existing:
            raise
        item = existing

    return SavedLeadItem(
        id=item.id,
        user_id=item.user_id,
        route_id=item.route_id,
        business_id=item.business_id,
        status=item.status,
        priority=item.priority,
        next_follow_up_at=item.next_follow_up_at,
        last_contact_attempt_at=item.last_contact_attempt_at,
    )


@router.get("", response_model=list[SavedLeadItem])
async def list_saved_leads(
    status: str | None = Query(default=None),
    due_before: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedLeadItem]:
    q = _saved_leads_base_query(user.id)
    if status:
        q = q.where(SavedLead.status == status)
    if due_before:
        q = q.where(SavedLead.next_follow_up_at.is_not(None), SavedLead.next_follow_up_at <= due_before)
    q = q.order_by(SavedLead.next_follow_up_at.asc().nulls_last(), SavedLead.created_at.desc()).limit(limit).offset(offset)
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

    overdue_rows = (
        await db.execute(
            base.where(
                unresolved,
                SavedLead.next_follow_up_at.is_not(None),
                SavedLead.next_follow_up_at < start_of_today,
            )
            .order_by(SavedLead.next_follow_up_at.asc())
            .limit(25)
        )
    ).all()
    due_today_rows = (
        await db.execute(
            base.where(
                unresolved,
                SavedLead.next_follow_up_at.is_not(None),
                SavedLead.next_follow_up_at >= start_of_today,
                SavedLead.next_follow_up_at < start_of_tomorrow,
            )
            .order_by(SavedLead.next_follow_up_at.asc())
            .limit(25)
        )
    ).all()
    untouched_rows = (
        await db.execute(
            base.where(
                SavedLead.status == "saved",
                SavedLead.last_contact_attempt_at.is_(None),
                LeadScore.final_score >= 70,
            )
            .order_by(LeadScore.final_score.desc(), SavedLead.created_at.asc())
            .limit(5)
        )
    ).all()

    latest_route = (
        await db.execute(
            select(Route).where(Route.user_id == user.id).order_by(Route.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    recent_route: TodayRecentRoute | None = None
    if latest_route:
        unsaved_count = await db.scalar(
            select(func.count())
            .where(
                RouteCandidate.route_id == latest_route.id,
                ~exists(
                    select(SavedLead.id).where(
                        and_(
                            SavedLead.user_id == user.id,
                            SavedLead.business_id == RouteCandidate.business_id,
                        )
                    )
                ),
            )
        )
        recent_route = TodayRecentRoute(
            route_id=latest_route.id,
            label=_format_route_label(latest_route.origin_label, latest_route.destination_label)
            or "Recent route",
            unsaved_lead_count=int(unsaved_count or 0),
        )

    return SavedLeadsTodayResponse(
        overdue=await _hydrate_saved_lead_items(db, user.id, overdue_rows),
        due_today=await _hydrate_saved_lead_items(db, user.id, due_today_rows),
        high_priority_untouched=await _hydrate_saved_lead_items(db, user.id, untouched_rows),
        recent_route=recent_route,
    )


@router.patch("/{saved_lead_id}", response_model=SavedLeadItem)
async def update_saved_lead(
    saved_lead_id: UUID,
    payload: UpdateSavedLeadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    item = (await db.execute(select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id))).scalar_one_or_none()
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
    await db.commit()

    return SavedLeadItem(
        id=item.id,
        user_id=item.user_id,
        route_id=item.route_id,
        business_id=item.business_id,
        status=item.status,
        priority=item.priority,
        next_follow_up_at=item.next_follow_up_at,
        last_contact_attempt_at=item.last_contact_attempt_at,
    )


@router.delete("/{saved_lead_id}")
async def delete_saved_lead(
    saved_lead_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_rate_limit(f"rl:saved_leads_write:{user.id}", limit=60, window_seconds=3600)
    item = (await db.execute(select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Saved lead not found")
    await db.delete(item)
    await db.commit()
    return {"message": "deleted"}
