from uuid import UUID

from pydantic import BaseModel


class LeadExplanation(BaseModel):
    fit: str
    distance: str
    actionability: str


class LeadItem(BaseModel):
    business_id: UUID
    name: str
    insurance_class: str | None
    address: str | None
    phone: str | None
    website: str | None
    final_score: int
    fit_score: int
    distance_score: int
    actionability_score: int
    distance_from_route_m: float
    explanation: LeadExplanation
    score_version: str | None = None
    rank_reason_v2: list[str] | None = None
    lat: float | None = None
    lng: float | None = None


class LeadsResponse(BaseModel):
    route_id: UUID
    leads: list[LeadItem]
    total: int
    filtered: int
