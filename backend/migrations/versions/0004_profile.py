"""Onboarding preferences and editable taxonomy."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("goals", "interests", "regions"):
        columns = [
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False, unique=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
        ]
        if name == "interests":
            columns.append(
                sa.Column(
                    "kind",
                    sa.Enum(
                        "SECTOR",
                        "THEME",
                        native_enum=False,
                        create_constraint=True,
                        name="interest_kind",
                    ),
                    nullable=False,
                )
            )
        op.create_table(name, *columns)
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "experience",
            sa.Enum(
                "NEW",
                "SOME",
                "REGULAR",
                "EXPERIENCED",
                native_enum=False,
                create_constraint=True,
                name="experience",
            ),
            nullable=False,
        ),
        sa.Column(
            "investment_horizon",
            sa.Enum(
                "UNDER_ONE",
                "ONE_THREE",
                "THREE_FIVE",
                "FIVE_PLUS",
                native_enum=False,
                create_constraint=True,
                name="horizon",
            ),
            nullable=False,
        ),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, column, target in (
        ("user_goals", "goal_id", "goals"),
        ("user_interests", "interest_id", "interests"),
        ("user_excluded_interests", "interest_id", "interests"),
        ("user_regions", "region_id", "regions"),
    ):
        op.create_table(
            name,
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column(column, sa.Uuid(), sa.ForeignKey(target + ".id"), primary_key=True),
        )


def downgrade():
    for name in (
        "user_regions",
        "user_excluded_interests",
        "user_interests",
        "user_goals",
        "user_profiles",
        "regions",
        "interests",
        "goals",
    ):
        op.drop_table(name)
