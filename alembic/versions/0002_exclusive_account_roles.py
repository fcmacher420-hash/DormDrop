"""Add exclusive buyer and seller account profiles.

Existing sellers and pending seller applicants retain their seller role.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_account_roles"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("account_type", sa.String(20), nullable=False, server_default="buyer"))
    op.add_column("users", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("business_name", sa.String(150), nullable=True))
    op.execute("UPDATE users SET account_type = 'seller' WHERE is_seller = 1")
    op.execute("UPDATE users SET account_type = 'admin' WHERE is_admin = 1")
    op.execute("UPDATE users SET account_type = 'seller' WHERE is_admin = 0 AND id IN (SELECT user_id FROM seller_requests WHERE status = 'pending')")


def downgrade():
    op.drop_column("users", "business_name")
    op.drop_column("users", "country")
    op.drop_column("users", "account_type")
