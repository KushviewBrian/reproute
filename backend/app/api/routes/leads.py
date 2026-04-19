from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.route import Route
from app.models.user import User
from app.schemas.lead import LeadGroup, LeadItem, LeadsResponse
from app.services.enrichment_service import enrich_route_top_leads
from app.services.lead_service import VALID_SORT_BY, fetch_leads
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter()

VALID_SORT_BY_LIST = sorted(VALID_SORT_BY)


@router.get("/{route_id}/leads", response_model=LeadsResponse)
async def get_route_leads(
    route_id: UUID,
    background_tasks: BackgroundTasks,
    min_score: int = Query(default=40, ge=0, le=100),
    has_phone: bool | None = None,
    has_website: bool | None = None,
    insurance_class: list[str] | None = Query(default=None),
    score_version: str | None = Query(default=None, pattern="^(v1|v2)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    # Phase 10 params
    sort_by: str = Query(default="score"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    blue_collar: bool | None = None,
    has_owner_name: bool | None = None,
    min_validation_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    validation_state: str | None = None,
    operating_status: str | None = None,
    score_band: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    group_by: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadsResponse:
    await enforce_rate_limit(f"rl:get_leads:{user.id}", limit=180, window_seconds=60)

    sort_by = sort_by if isinstance(sort_by, str) else "score"
    if sort_by not in VALID_SORT_BY:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(
            status_code=422,
            detail=f"Invalid sort_by '{sort_by}'. Must be one of: {VALID_SORT_BY_LIST}",
        )

    route = await db.get(Route, route_id)
    if not route or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Route not found")

    leads, total, filtered, groups = await fetch_leads(
        db,
        route_id=route_id,
        min_score=min_score,
        has_phone=has_phone,
        has_website=has_website,
        insurance_classes=insurance_class,
        requested_score_version=score_version,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        blue_collar=blue_collar,
        has_owner_name=has_owner_name,
        min_validation_confidence=min_validation_confidence,
        validation_state=validation_state,
        operating_status=operating_status,
        score_band=score_band,
        group_by=group_by,
    )

    if offset == 0:
        from app.utils.redis_client import redis_client as _redis
        lock_key = f"enrich:route_fired:{route_id}"
        already_fired = await _redis.get(lock_key)
        if not already_fired:
            await _redis.set(lock_key, "1", ex=3600)
            background_tasks.add_task(enrich_route_top_leads, route_id)

    groups_out = None
    if groups is not None:
        groups_out = [LeadGroup(
            key=g["key"],
            label=g["label"],
            count=g["count"],
            leads=[LeadItem(**lead) for lead in g["leads"]],
        ) for g in groups]

    return LeadsResponse(
        route_id=route_id,
        leads=[LeadItem(**row) for row in leads],
        total=total,
        filtered=filtered,
        groups=groups_out,
    )
