from uuid import UUID

from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class CreateSavedLeadRequest(BaseModel):
    business_id: UUID
    route_id: UUID | None = None


class UpdateSavedLeadRequest(BaseModel):
    status: Literal["saved", "visited", "called", "follow_up", "not_interested"] | None = None
    priority: int | None = None
    next_follow_up_at: datetime | None = None
    last_contact_attempt_at: datetime | None = None


class SavedLeadItem(BaseModel):
    id: UUID
    user_id: UUID
    route_id: UUID | None
    business_id: UUID
    status: str
    priority: int
    next_follow_up_at: datetime | None = None
    last_contact_attempt_at: datetime | None = None
    business_name: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    route_label: str | None = None
    final_score: int | None = None
    latest_note_text: str | None = None
    latest_note_created_at: datetime | None = None


class TodayRecentRoute(BaseModel):
    route_id: UUID
    label: str
    unsaved_lead_count: int


class SavedLeadsTodayResponse(BaseModel):
    overdue: list[SavedLeadItem]
    due_today: list[SavedLeadItem]
    high_priority_untouched: list[SavedLeadItem]
    recent_route: TodayRecentRoute | None = None
