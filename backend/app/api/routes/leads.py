from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.route import Route
from app.models.user import User
from app.schemas.lead import LeadItem, LeadsResponse
from app.services.lead_service import fetch_leads

router = APIRouter()


@router.get("/{route_id}/leads", response_model=LeadsResponse)
async def get_route_leads(
    route_id: UUID,
    min_score: int = Query(default=40, ge=0, le=100),
    has_phone: bool | None = None,
    has_website: bool | None = None,
    insurance_class: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadsResponse:
    route = await db.get(Route, route_id)
    if not route or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Route not found")

    leads, total, filtered = await fetch_leads(
        db,
        route_id=route_id,
        min_score=min_score,
        has_phone=has_phone,
        has_website=has_website,
        insurance_classes=insurance_class,
        limit=limit,
        offset=offset,
    )
    return LeadsResponse(route_id=route_id, leads=[LeadItem(**row) for row in leads], total=total, filtered=filtered)
