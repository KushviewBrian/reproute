from uuid import UUID

from pydantic import BaseModel, Field


class Waypoint(BaseModel):
    label: str
    lat: float
    lng: float


class CreateRouteRequest(BaseModel):
    origin_label: str
    origin_lat: float
    origin_lng: float
    destination_label: str
    destination_lat: float
    destination_lng: float
    corridor_width_meters: int = Field(default=1609, ge=100, le=10000)
    waypoints: list[Waypoint] = Field(default_factory=list)


class CreateRouteResponse(BaseModel):
    route_id: UUID
    route_distance_meters: int
    route_duration_seconds: int
    lead_count: int
    route_geojson: dict


class RouteSummaryResponse(BaseModel):
    route_id: UUID
    origin_label: str | None
    destination_label: str | None
    route_distance_meters: int | None
    route_duration_seconds: int | None
    candidate_count: int


class PatchRouteRequest(BaseModel):
    corridor_width_meters: int = Field(ge=100, le=10000)
