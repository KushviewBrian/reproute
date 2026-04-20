from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TriggerValidationRequest(BaseModel):
    requested_checks: list[str] = Field(default_factory=lambda: ["website", "phone"])


class BatchValidationRequest(BaseModel):
    business_ids: list[UUID] = Field(default_factory=list, max_length=100)


class TriggerValidationResponse(BaseModel):
    run_id: UUID
    status: str


class ValidationFieldState(BaseModel):
    field_name: str
    state: str | None = None
    confidence: float | None = None
    failure_class: str | None = None
    value_current: str | None = None
    value_normalized: str | None = None
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    evidence_json: dict | None = None
    pinned_by_user: bool = False


class ValidationRunState(BaseModel):
    run_id: UUID
    business_id: UUID
    status: str
    requested_checks: list[str] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class ValidationStateResponse(BaseModel):
    run: ValidationRunState | None = None
    fields: list[ValidationFieldState] = Field(default_factory=list)
    overall_confidence: float | None = None
    overall_label: str = "Unchecked"


class AdminRunDueResponse(BaseModel):
    queued: int
    completed: int
    failed: int


class PinFieldRequest(BaseModel):
    pinned: bool


class PinFieldResponse(BaseModel):
    field_name: str
    pinned_by_user: bool


class AdminPruneResponse(BaseModel):
    deleted: int
