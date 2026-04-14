from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.geocode import GeocodeResponse
from app.services.geocode_service import geocode
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter()


@router.get("", response_model=GeocodeResponse)
async def geocode_query(
    q: str | None = Query(default=None, min_length=2),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> GeocodeResponse:
    await enforce_rate_limit(f"rl:geocode:{user.id}", limit=30, window_seconds=60)
    results, degraded = await geocode(query=q, lat=lat, lng=lng)
    return GeocodeResponse(results=results, degraded=degraded)
