from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.validation import (
    AdminRunDueResponse,
    TriggerValidationRequest,
    TriggerValidationResponse,
    ValidationFieldState,
    ValidationRunState,
    ValidationStateResponse,
)
from app.services.validation_service import (
    enqueue_validation_run,
    get_validation_state,
    process_queued_runs,
    process_run_by_id,
    reserve_validation_caps,
    user_can_access_business,
    verify_admin_hmac,
)
from app.utils.rate_limit import enforce_rate_limit

lead_router = APIRouter()
admin_router = APIRouter()


@lead_router.post("/{business_id}/validate", response_model=TriggerValidationResponse)
async def trigger_validation(
    business_id: UUID,
    payload: TriggerValidationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TriggerValidationResponse:
    await enforce_rate_limit(f"rl:validation_trigger:{user.id}", limit=30, window_seconds=3600)
    if not await user_can_access_business(db, user.id, business_id):
        raise HTTPException(status_code=404, detail="Business not found")
    try:
        await reserve_validation_caps(user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run = await enqueue_validation_run(
        db,
        business_id=business_id,
        user_id=user.id,
        requested_checks=payload.requested_checks,
    )
    run, _ = await process_run_by_id(db, run.id)
    return TriggerValidationResponse(run_id=run.id, status=run.status)


@lead_router.get("/{business_id}/validation", response_model=ValidationStateResponse)
async def read_validation_state(
    business_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationStateResponse:
    if not await user_can_access_business(db, user.id, business_id):
        raise HTTPException(status_code=404, detail="Business not found")
    run, fields, conf, label = await get_validation_state(db, business_id)
    return ValidationStateResponse(
        run=ValidationRunState(
            run_id=run.id,
            business_id=run.business_id,
            status=run.status,
            requested_checks=run.requested_checks,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_message=run.error_message,
        ) if run else None,
        fields=[
            ValidationFieldState(
                field_name=f.field_name,
                state=f.state,
                confidence=float(f.confidence) if f.confidence is not None else None,
                failure_class=f.failure_class,
                value_current=f.value_current,
                value_normalized=f.value_normalized,
                evidence_json=f.evidence_json,
                last_checked_at=f.last_checked_at,
                next_check_at=f.next_check_at,
            )
            for f in fields
        ],
        overall_confidence=conf,
        overall_label=label,
    )


@admin_router.post("/run-due", response_model=AdminRunDueResponse)
async def run_due_validations(
    limit: int = Query(default=10, ge=1, le=50),
    x_admin_timestamp: str | None = Header(default=None, alias="X-Admin-Timestamp"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> AdminRunDueResponse:
    if not x_admin_timestamp or not x_admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin token headers")
    try:
        verify_admin_hmac(x_admin_timestamp, x_admin_token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    queued, completed, failed = await process_queued_runs(limit=limit)
    return AdminRunDueResponse(queued=queued, completed=completed, failed=failed)
