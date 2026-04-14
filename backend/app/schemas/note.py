from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateNoteRequest(BaseModel):
    business_id: UUID
    route_id: UUID | None = None
    note_text: str
    outcome_status: str | None = None
    next_action: str | None = None


class UpdateNoteRequest(BaseModel):
    note_text: str | None = None
    outcome_status: str | None = None
    next_action: str | None = None


class NoteItem(BaseModel):
    id: UUID
    business_id: UUID
    route_id: UUID | None
    note_text: str
    outcome_status: str | None
    next_action: str | None
    created_at: datetime
