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
    owner_name: str | None = None  # Phase 10: manual rep entry
    employee_count_estimate: int | None = None
    employee_count_band: str | None = None


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
    # Phase 10
    is_blue_collar: bool = False
    owner_name: str | None = None
    owner_name_source: str | None = None
    owner_name_confidence: float | None = None
    employee_count_estimate: int | None = None
    employee_count_band: str | None = None
    employee_count_source: str | None = None
    employee_count_confidence: float | None = None
    insurance_class: str | None = None
    operating_status: str | None = None
    validation_state: str | None = None
    saved_at: datetime | None = None


class SavedLeadGroup(BaseModel):
    key: str
    label: str
    count: int
    leads: list[SavedLeadItem]


class TodayRecentRoute(BaseModel):
    route_id: UUID
    label: str
    unsaved_lead_count: int


class SavedLeadsTodayResponse(BaseModel):
    overdue: list[SavedLeadItem]
    due_today: list[SavedLeadItem]
    high_priority_untouched: list[SavedLeadItem]
    recent_route: TodayRecentRoute | None = None
    # Phase 10 new sections
    blue_collar_today: list[SavedLeadItem] = []
    has_owner_name: list[SavedLeadItem] = []
