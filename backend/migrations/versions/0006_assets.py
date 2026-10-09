"""Underlying assets, demo market data, themes, tokens and asset risks."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum("STOCK", "ETF", native_enum=False, create_constraint=True, name="asset_type"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sector", sa.String(128)),
        sa.Column("industry", sa.String(128)),
        sa.Column("country", sa.String(128)),
        sa.Column("region", sa.String(64)),
        sa.Column("market", sa.String(128)),
        sa.Column("logo_url", sa.Text()),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("symbol", "region", "sector", "asset_type"):
        op.create_index("ix_assets_" + column, "assets", [column], unique=column == "symbol")
    op.create_table(
        "asset_themes",
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("interest_id", sa.Uuid(), sa.ForeignKey("interests.id"), primary_key=True),
    )
    op.create_table(
        "asset_fundamentals",
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), primary_key=True),
        *[
            sa.Column(key, sa.Numeric(24, 6))
            for key in (
                "price",
                "market_cap",
                "pe",
                "eps",
                "revenue",
                "revenue_growth",
                "net_income",
                "debt",
                "cash_flow",
                "dividend",
                "dividend_yield",
            )
        ],
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "asset_prices",
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), primary_key=True),
        *[
            sa.Column(key, sa.Numeric(24, 6), nullable=False)
            for key in ("open", "high", "low", "close")
        ],
        sa.Column("volume", sa.Numeric(24, 6)),
    )
    op.create_table(
        "tokenized_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("token_name", sa.String(255), nullable=False),
        *[
            sa.Column(key, sa.String(255))
            for key in ("issuer", "tokenization_provider", "oracle_provider", "availability")
        ],
        *[
            sa.Column(key, sa.Text())
            for key in (
                "backing",
                "proof_of_reserves_url",
                "oracle_reference",
                "corporate_actions_info",
                "external_buy_url",
            )
        ],
        sa.Column("external_provider_id", sa.String(64)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id", "symbol", name="uq_asset_token_symbol"),
    )
    op.create_index("ix_tokenized_assets_asset_id", "tokenized_assets", ["asset_id"])
    op.create_table(
        "asset_risks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_asset_risks_asset_id", "asset_risks", ["asset_id"])


def downgrade():
    for table in (
        "asset_risks",
        "tokenized_assets",
        "asset_prices",
        "asset_fundamentals",
        "asset_themes",
        "assets",
    ):
        op.drop_table(table)
