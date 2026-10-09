"""Versioned legal documents and per-user consent records."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "type",
            sa.Enum(
                "TERMS_OF_USE",
                "PRIVACY_POLICY",
                "PERSONAL_DATA_CONSENT",
                native_enum=False,
                create_constraint=True,
                name="legal_document_type",
            ),
            nullable=False,
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("type", "version", name="uq_legal_type_version"),
    )
    op.create_index(
        "uq_legal_active_type",
        "legal_documents",
        ["type"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        sqlite_where=sa.text("active = 1"),
    )
    op.create_table(
        "user_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "legal_document_id", sa.Uuid(), sa.ForeignKey("legal_documents.id"), nullable=False
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "legal_document_id", name="uq_user_document_consent"),
    )


def downgrade():
    op.drop_table("user_consents")
    op.drop_table("legal_documents")
