import uuid

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Route(Base):
    __tablename__ = "route"
    __table_args__ = (
        Index("idx_route_geom", "route_geom", postgresql_using="gist"),
        Index("idx_route_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    origin_label: Mapped[str | None] = mapped_column(String)
    destination_label: Mapped[str | None] = mapped_column(String)
    origin_lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    origin_lng: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    destination_lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    destination_lng: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    route_geom: Mapped[str | None] = mapped_column(Geography(geometry_type="LINESTRING", srid=4326))
    route_distance_meters: Mapped[int | None] = mapped_column(Integer)
    route_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    corridor_width_meters: Mapped[int] = mapped_column(Integer, default=1609)
    ors_response_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
