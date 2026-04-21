"""optimization indexes for saved_lead and lead_field_validation

Revision ID: 0010_optimization_indexes
Revises: 0009_owner_employee_reliability
Create Date: 2026-04-21
"""

from alembic import op

revision = "0010_optimization_indexes"
down_revision = "0009_owner_employee_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Speeds up all WHERE user_id = ? queries on saved_lead (list, today, export)
    op.create_index("idx_saved_lead_user", "saved_lead", ["user_id"])

    # Speeds up today-dashboard sort / filter on next_follow_up_at per user
    op.create_index("idx_saved_lead_user_followup", "saved_lead", ["user_id", "next_follow_up_at"])

    # Speeds up the validation confidence subquery GROUP BY business_id
    op.create_index("idx_lead_field_validation_business", "lead_field_validation", ["business_id"])


def downgrade() -> None:
    op.drop_index("idx_saved_lead_user", table_name="saved_lead")
    op.drop_index("idx_saved_lead_user_followup", table_name="saved_lead")
    op.drop_index("idx_lead_field_validation_business", table_name="lead_field_validation")
