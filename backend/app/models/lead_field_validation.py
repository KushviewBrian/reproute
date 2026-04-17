import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadFieldValidation(Base):
    __tablename__ = "lead_field_validation"
    __table_args__ = (
        UniqueConstraint("business_id", "field_name", name="uq_lead_field_validation_business_field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("business.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    value_current: Mapped[str | None] = mapped_column(Text)
    value_normalized: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    failure_class: Mapped[str | None] = mapped_column(String)
    last_checked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    pinned_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
