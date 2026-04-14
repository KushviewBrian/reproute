import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadScore(Base):
    __tablename__ = "lead_score"
    __table_args__ = (
        UniqueConstraint("route_id", "business_id", name="uq_lead_score_route_business"),
        CheckConstraint("fit_score BETWEEN 0 AND 100", name="chk_fit_score"),
        CheckConstraint("distance_score BETWEEN 0 AND 100", name="chk_distance_score"),
        CheckConstraint("actionability_score BETWEEN 0 AND 100", name="chk_actionability_score"),
        CheckConstraint("final_score BETWEEN 0 AND 100", name="chk_final_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("route.id", ondelete="CASCADE"), nullable=False)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("business.id"), nullable=False)
    fit_score: Mapped[int] = mapped_column(SmallInteger)
    distance_score: Mapped[int] = mapped_column(SmallInteger)
    actionability_score: Mapped[int] = mapped_column(SmallInteger)
    final_score: Mapped[int] = mapped_column(SmallInteger)
    score_version: Mapped[str] = mapped_column(String, default="v1")
    score_explanation_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
