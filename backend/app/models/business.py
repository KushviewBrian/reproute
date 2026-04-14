import uuid

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Business(Base):
    __tablename__ = "business"
    __table_args__ = (
        UniqueConstraint("external_source", "external_id", name="uq_business_external"),
        Index("idx_business_geom", "geom", postgresql_using="gist"),
        Index("idx_business_insurance_class", "insurance_class"),
        Index("idx_business_operating_status", "operating_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_source: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String)
    brand_name: Mapped[str | None] = mapped_column(String)
    category_primary: Mapped[str | None] = mapped_column(String)
    category_secondary: Mapped[str | None] = mapped_column(String)
    insurance_class: Mapped[str | None] = mapped_column(String)
    address_line1: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    postal_code: Mapped[str | None] = mapped_column(String)
    country: Mapped[str] = mapped_column(String, server_default="US")
    phone: Mapped[str | None] = mapped_column(String)
    website: Mapped[str | None] = mapped_column(String)
    operating_status: Mapped[str | None] = mapped_column(String)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    geom: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    has_phone: Mapped[bool] = mapped_column(default=False)
    has_website: Mapped[bool] = mapped_column(default=False)
    has_address: Mapped[bool] = mapped_column(default=False)
    source_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    last_validated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
