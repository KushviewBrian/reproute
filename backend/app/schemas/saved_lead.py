from uuid import UUID

from pydantic import BaseModel


class CreateSavedLeadRequest(BaseModel):
    business_id: UUID
    route_id: UUID | None = None


class UpdateSavedLeadRequest(BaseModel):
    status: str | None = None
    priority: int | None = None


class SavedLeadItem(BaseModel):
    id: UUID
    user_id: UUID
    route_id: UUID | None
    business_id: UUID
    status: str
    priority: int
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
