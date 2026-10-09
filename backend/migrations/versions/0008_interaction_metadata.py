"""Optional interaction event metadata."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("asset_interactions", sa.Column("metadata", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("asset_interactions", "metadata")
