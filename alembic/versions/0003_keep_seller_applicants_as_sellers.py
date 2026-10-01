"""Keep every legacy seller applicant in the seller account role."""
from alembic import op

revision = "0003_seller_applicant_roles"
down_revision = "0002_account_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET account_type = 'seller' WHERE is_admin = 0 AND id IN (SELECT user_id FROM seller_requests)")


def downgrade():
    # Account role is durable user data; do not demote applicants on downgrade.
    pass
