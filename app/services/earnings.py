"""Seller sales and balance calculations (exact Decimal arithmetic, per-order commission rate)."""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.money import as_decimal, to_money
from app.models import Commission, Listing, Order, OrderItem, SellerPayout

ZERO = Decimal("0.00")


def seller_sales(db: Session, seller_id: int) -> list[dict]:
    """One row per order line sold by the seller. Net uses the commission rate stored on that order."""
    rows = db.execute(
        select(Order.id.label("order_pk"), Order.order_id.label("public_order_id"), Order.status.label("order_status"),
               OrderItem.listing_id.label("listing_id"), OrderItem.quantity.label("quantity"),
               OrderItem.unit_price.label("unit_price"), Commission.rate.label("rate"))
        .select_from(OrderItem)
        .join(Listing, Listing.id == OrderItem.listing_id)
        .join(Order, Order.id == OrderItem.order_id)
        .outerjoin(Commission, Commission.order_id == Order.id)
        .where(Listing.seller_id == seller_id)
        .order_by(Order.created_at.desc(), OrderItem.id)
    ).all()
    sales = []
    for row in rows:
        rate = as_decimal(row.rate) if row.rate is not None else as_decimal(settings.commission_rate)
        gross = to_money(row.unit_price) * row.quantity
        sales.append({"order_pk": row.order_pk, "order_id": row.public_order_id, "status": row.order_status,
                      "listing_id": row.listing_id, "quantity": row.quantity, "gross": gross,
                      "net": to_money(gross * (Decimal(1) - rate))})
    return sales


def sole_seller_orders(db: Session, order_pks: list[int]) -> set[int]:
    """Order primary keys whose items all belong to a single seller (only those sellers may advance status)."""
    if not order_pks:
        return set()
    rows = db.execute(
        select(OrderItem.order_id, func.count(Listing.seller_id.distinct()))
        .join(Listing, Listing.id == OrderItem.listing_id)
        .where(OrderItem.order_id.in_(order_pks))
        .group_by(OrderItem.order_id)
    ).all()
    return {order_pk for order_pk, seller_count in rows if seller_count == 1}


def paid_out(db: Session, seller_id: int) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(SellerPayout.amount), 0)).where(SellerPayout.seller_id == seller_id))
    return to_money(total or 0)


def summary(db: Session, seller_id: int) -> dict:
    """Totals for the dashboard. Only delivered orders count towards what can be paid out."""
    sales = seller_sales(db, seller_id)
    gross = sum((s["gross"] for s in sales), ZERO)
    net = sum((s["net"] for s in sales), ZERO)
    net_delivered = sum((s["net"] for s in sales if s["status"] == "delivered"), ZERO)
    paid = paid_out(db, seller_id)
    return {"sales": sales, "gross_sales": gross, "revenue_after_commission": net, "paid_out": paid,
            "available_for_payout": max(ZERO, net_delivered - paid)}
