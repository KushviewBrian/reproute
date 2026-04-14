from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.business import Business
from app.models.user import User

router = APIRouter()


@router.get("/{business_id}")
async def get_business(
    business_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = user
    business = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    return {
        "business_id": str(business.id),
        "name": business.name,
        "insurance_class": business.insurance_class,
        "address": {
            "line1": business.address_line1,
            "city": business.city,
            "state": business.state,
            "postal_code": business.postal_code,
            "country": business.country,
        },
        "phone": business.phone,
        "website": business.website,
        "operating_status": business.operating_status,
        "confidence_score": float(business.confidence_score) if business.confidence_score is not None else None,
    }
