"""Interaction history and current independent bookmark state."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_interaction_states",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("liked", sa.Boolean(), nullable=False),
        sa.Column("disliked", sa.Boolean(), nullable=False),
        sa.Column("saved", sa.Boolean(), nullable=False),
        sa.CheckConstraint("NOT (liked AND disliked)", name="ck_interaction_exclusive"),
    )
    op.create_table(
        "asset_interactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('LIKE','UNLIKE','DISLIKE','REMOVE_DISLIKE',"
            "'SAVE','UNSAVE','VIEW','BUY_CLICK')",
            name="ck_interaction_type",
        ),
    )
    for name, columns in (
        ("user_asset", ["user_id", "asset_id"]),
        ("user_type", ["user_id", "type"]),
        ("asset_type", ["asset_id", "type"]),
    ):
        op.create_index("ix_interactions_" + name, "asset_interactions", columns)
    op.create_index("ix_asset_interactions_created_at", "asset_interactions", ["created_at"])


def downgrade():
    op.drop_table("asset_interactions")
    op.drop_table("asset_interaction_states")
