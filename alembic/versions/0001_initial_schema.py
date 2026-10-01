"""Create the initial DormDrop schema with explicit tables (no metadata.create_all).

Money columns are NUMERIC(12, 2); measurements are double precision.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("campus", sa.String(150), nullable=False),
        sa.Column("dorm", sa.String(150), nullable=False),
        sa.Column("is_verified", sa.Boolean, nullable=False),
        sa.Column("is_seller", sa.Boolean, nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False),
        sa.Column("is_suspended", sa.Boolean, nullable=False),
        sa.Column("rating_avg", sa.Float(53), nullable=False),
        sa.Column("verification_token", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "seller_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_seller_requests_user_id", "seller_requests", ["user_id"])

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("seller_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("length_cm", sa.Float(53), nullable=False),
        sa.Column("width_cm", sa.Float(53), nullable=False),
        sa.Column("height_cm", sa.Float(53), nullable=False),
        sa.Column("weight_kg", sa.Float(53), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_listings_seller_id", "listings", ["seller_id"])
    op.create_index("ix_listings_category", "listings", ["category"])
    op.create_index("ix_listings_status", "listings", ["status"])

    op.create_table(
        "listing_images",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
    )
    op.create_index("ix_listing_images_listing_id", "listing_images", ["listing_id"])

    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("buyer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.UniqueConstraint("buyer_id", "listing_id", name="uq_cart_buyer_listing"),
    )
    op.create_index("ix_cart_items_buyer_id", "cart_items", ["buyer_id"])
    op.create_index("ix_cart_items_listing_id", "cart_items", ["listing_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.String(20), nullable=False),
        sa.Column("buyer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subtotal", MONEY, nullable=False),
        sa.Column("shipping_fee", MONEY, nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("payment_ref", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_order_id", "orders", ["order_id"], unique=True)
    op.create_index("ix_orders_buyer_id", "orders", ["buyer_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", MONEY, nullable=False),
        sa.Column("item_shipping_fee", MONEY, nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commissions_order_id", "commissions", ["order_id"])

    op.create_table(
        "seller_payouts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("seller_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("processed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seller_payouts_seller_id", "seller_payouts", ["seller_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sender_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receiver_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index("ix_messages_receiver_id", "messages", ["receiver_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("buyer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("seller_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "seller_id", name="uq_review_order_seller"),
    )
    op.create_index("ix_reviews_order_id", "reviews", ["order_id"])
    op.create_index("ix_reviews_buyer_id", "reviews", ["buyer_id"])
    op.create_index("ix_reviews_seller_id", "reviews", ["seller_id"])


def downgrade():
    for table in ("reviews", "messages", "seller_payouts", "commissions", "order_items", "orders",
                  "cart_items", "listing_images", "listings", "seller_requests", "users"):
        op.drop_table(table)
