import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScoringFeedbackPrior(Base):
    __tablename__ = "scoring_feedback_prior"
    __table_args__ = (
        UniqueConstraint(
            "calibration_version",
            "insurance_class",
            "has_phone",
            "has_website",
            "distance_band",
            name="uq_scoring_feedback_prior_segment",
        ),
        Index("idx_scoring_feedback_prior_version", "calibration_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calibration_version: Mapped[str] = mapped_column(String, nullable=False)
    insurance_class: Mapped[str | None] = mapped_column(String)
    has_phone: Mapped[bool | None] = mapped_column(Boolean)
    has_website: Mapped[bool | None] = mapped_column(Boolean)
    distance_band: Mapped[str] = mapped_column(String, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    save_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contacted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prior_save: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False, default=0.0)
    prior_contact: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False, default=0.0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
