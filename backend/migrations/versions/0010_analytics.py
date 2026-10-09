"""Internal analytics events."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("properties", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analytics_event_created", "analytics_events", ["event_name", "created_at"])
    op.create_index("ix_analytics_user_created", "analytics_events", ["user_id", "created_at"])


def downgrade():
    op.drop_table("analytics_events")
