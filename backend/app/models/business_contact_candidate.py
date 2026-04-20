import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BusinessContactCandidate(Base):
    __tablename__ = "business_contact_candidate"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "field_key",
            "source",
            "value_hash",
            name="uq_bcc_business_field_source_hash",
        ),
        Index("idx_bcc_business_field_active", "business_id", "field_key", postgresql_where=text("is_active = true")),
        Index("idx_bcc_promoted_at", "promoted_at", postgresql_where=text("promoted_at IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("business.id"), nullable=False)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_numeric: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    observed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    value_hash: Mapped[str] = mapped_column(String, nullable=False)
