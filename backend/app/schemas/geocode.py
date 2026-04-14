from pydantic import BaseModel


class GeocodeResult(BaseModel):
    label: str
    lat: float
    lng: float
    bbox: list[float] | None = None


class GeocodeResponse(BaseModel):
    results: list[GeocodeResult]
    degraded: bool = False
