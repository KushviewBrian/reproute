from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.enrichment_service import enrich_business
from app.services.validation_service import user_can_access_business
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter()


class EnrichResponse(BaseModel):
    business_id: UUID
    enriched: bool
    osm_phone: str | None = None
    osm_website: str | None = None
    osm_enriched_at: str | None = None
    skipped_reason: str | None = None


@router.post("/{business_id}/enrich", response_model=EnrichResponse)
async def trigger_enrichment(
    business_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EnrichResponse:
    await enforce_rate_limit(f"rl:enrich_trigger:{user.id}", limit=30, window_seconds=3600)

    if not await user_can_access_business(db, user.id, business_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    try:
        ran = await enrich_business(db, business_id, user_id=user.id, force=False)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    from app.models.business import Business
    business = await db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    return EnrichResponse(
        business_id=business_id,
        enriched=ran,
        osm_phone=business.osm_phone,
        osm_website=business.osm_website,
        osm_enriched_at=business.osm_enriched_at.isoformat() if business.osm_enriched_at else None,
        skipped_reason="already_fresh" if not ran else None,
    )
