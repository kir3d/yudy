"""Versioned risk questionnaires and per-user assessment results."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "risk_questionnaires",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("conservative_max", sa.Integer(), nullable=False),
        sa.Column("balanced_max", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "conservative_max >= 0 AND conservative_max < balanced_max AND balanced_max < 100",
            name="ck_risk_thresholds",
        ),
    )
    op.create_index(
        "uq_risk_active",
        "risk_questionnaires",
        ["active"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        sqlite_where=sa.text("active = 1"),
    )
    op.create_table(
        "risk_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "questionnaire_id", sa.Uuid(), sa.ForeignKey("risk_questionnaires.id"), nullable=False
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("questionnaire_id", "code", name="uq_risk_question_code"),
    )
    op.create_index("ix_risk_questions_questionnaire_id", "risk_questions", ["questionnaire_id"])
    op.create_table(
        "risk_answer_options",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("risk_questions.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("question_id", "code", name="uq_risk_option_code"),
        sa.CheckConstraint("score >= 0", name="ck_risk_option_score"),
    )
    op.create_index("ix_risk_answer_options_question_id", "risk_answer_options", ["question_id"])
    op.create_table(
        "risk_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column(
            "risk_category",
            sa.Enum(
                "CONSERVATIVE",
                "BALANCED",
                "GROWTH",
                native_enum=False,
                create_constraint=True,
                name="risk_category",
            ),
            nullable=False,
        ),
        sa.Column(
            "questionnaire_version",
            sa.String(64),
            sa.ForeignKey("risk_questionnaires.version"),
            nullable=False,
        ),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_profile_score"),
    )


def downgrade():
    for name in ("risk_profiles", "risk_answer_options", "risk_questions", "risk_questionnaires"):
        op.drop_table(name)
