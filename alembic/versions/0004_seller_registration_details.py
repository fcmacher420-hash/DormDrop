"""Store the business and contact details collected on seller signup."""
import sqlalchemy as sa
from alembic import op

revision = "0004_seller_registration_details"
down_revision = "0003_seller_applicant_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("contact_person", sa.String(150), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(40), nullable=True))
    op.add_column("users", sa.Column("business_description", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("product_types", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("users", "product_types")
    op.drop_column("users", "business_description")
    op.drop_column("users", "phone")
    op.drop_column("users", "contact_person")
