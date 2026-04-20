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
    # Phase 10
    is_blue_collar: bool = False
    owner_name: str | None = None
    owner_name_source: str | None = None
    owner_name_confidence: float | None = None
    employee_count_estimate: int | None = None
    employee_count_band: str | None = None
    employee_count_source: str | None = None
    employee_count_confidence: float | None = None


class LeadGroup(BaseModel):
    key: str
    label: str
    count: int
    leads: list[LeadItem]


class LeadsResponse(BaseModel):
    route_id: UUID
    leads: list[LeadItem]
    total: int
    filtered: int
    # populated when group_by is requested
    groups: list[LeadGroup] | None = None
