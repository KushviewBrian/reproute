import uuid

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedLead(Base):
    __tablename__ = "saved_lead"
    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_saved_lead_user_business"),
        Index("idx_saved_lead_user", "user_id"),
        Index("idx_saved_lead_user_followup", "user_id", "next_follow_up_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    route_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("route.id"))
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("business.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="saved")
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_follow_up_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    last_contact_attempt_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
