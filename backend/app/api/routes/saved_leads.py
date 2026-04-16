from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.business import Business
from app.models.saved_lead import SavedLead
from app.models.user import User
from app.schemas.saved_lead import CreateSavedLeadRequest, SavedLeadItem, UpdateSavedLeadRequest

router = APIRouter()


@router.post("", response_model=SavedLeadItem)
async def create_saved_lead(
    payload: CreateSavedLeadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    item = SavedLead(user_id=user.id, business_id=payload.business_id, route_id=payload.route_id)
    db.add(item)
    await db.commit()
    return SavedLeadItem(
        id=item.id,
        user_id=item.user_id,
        route_id=item.route_id,
        business_id=item.business_id,
        status=item.status,
        priority=item.priority,
    )


@router.get("", response_model=list[SavedLeadItem])
async def list_saved_leads(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedLeadItem]:
    q = (
        select(SavedLead, Business.name, Business.phone, Business.address_line1, Business.city, Business.state)
        .join(Business, Business.id == SavedLead.business_id, isouter=True)
        .where(SavedLead.user_id == user.id)
    )
    if status:
        q = q.where(SavedLead.status == status)
    q = q.limit(limit).offset(offset)
    rows = (await db.execute(q)).all()
    return [
        SavedLeadItem(
            id=i.SavedLead.id,
            user_id=i.SavedLead.user_id,
            route_id=i.SavedLead.route_id,
            business_id=i.SavedLead.business_id,
            status=i.SavedLead.status,
            priority=i.SavedLead.priority,
            business_name=i.name,
            phone=i.phone,
            address=", ".join(p for p in [i.address_line1, i.city, i.state] if p) or None,
        )
        for i in rows
    ]


@router.patch("/{saved_lead_id}", response_model=SavedLeadItem)
async def update_saved_lead(
    saved_lead_id: UUID,
    payload: UpdateSavedLeadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedLeadItem:
    item = (await db.execute(select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Saved lead not found")

    if payload.status is not None:
        item.status = payload.status
    if payload.priority is not None:
        item.priority = payload.priority
    await db.commit()

    return SavedLeadItem(
        id=item.id,
        user_id=item.user_id,
        route_id=item.route_id,
        business_id=item.business_id,
        status=item.status,
        priority=item.priority,
    )


@router.delete("/{saved_lead_id}")
async def delete_saved_lead(
    saved_lead_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = (await db.execute(select(SavedLead).where(SavedLead.id == saved_lead_id, SavedLead.user_id == user.id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Saved lead not found")
    await db.delete(item)
    await db.commit()
    return {"message": "deleted"}
