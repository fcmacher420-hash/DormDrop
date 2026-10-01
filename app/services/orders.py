from datetime import datetime, timezone
from decimal import Decimal
import random
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.money import as_decimal, to_money
from app.models import CartItem, Commission, Listing, Order, OrderItem
from app.repositories.repository import Repository
from app.services.payments import provider_for
from app.services.shipping import shipping_fee

def generate_order_id(db: Session, now: datetime | None = None, rand: random.Random | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    rand = rand or random.SystemRandom()
    date_part = now.strftime("%Y%m%d")
    for _ in range(100):
        candidate = f"DD-{date_part}-{rand.randint(0, 9999):04d}"
        if not db.scalar(select(Order.id).where(Order.order_id == candidate)):
            return candidate
    raise RuntimeError("Could not allocate a unique order ID")

def _checkout_once(db: Session, buyer_id: int, method: str, details: str, payment: dict) -> Order:
    """Place a paid order; order, stock, line items, cart and commission commit atomically.

    `payment` caches the provider reference so a retry after an order-ID collision never charges twice.
    """
    repo = Repository(db)
    cart = repo.cart(buyer_id)
    if not cart: raise ValueError("Your cart is empty")
    lines = []
    for entry in cart:
        # Lock stock rows so concurrent MySQL checkouts cannot consume the same units.
        # populate_existing forces the locked row's current values to replace any stale cached copy.
        listing = db.scalar(select(Listing).where(Listing.id == entry.listing_id)
                            .with_for_update().execution_options(populate_existing=True))
        if listing is None or listing.status != "approved": raise ValueError("A cart listing is no longer available")
        if listing.seller_id == buyer_id: raise ValueError("You cannot buy your own listing")
        if listing.quantity < entry.quantity: raise ValueError(f"Not enough stock for {listing.title}")
        fee = shipping_fee(listing.length_cm, listing.width_cm, listing.height_cm, listing.weight_kg)
        lines.append((entry, listing, fee))
    subtotal = sum((to_money(item.price) * entry.quantity for entry, item, _ in lines), Decimal("0.00"))
    shipping = sum((fee * entry.quantity for entry, _, fee in lines), Decimal("0.00"))
    total = subtotal + shipping
    if "ref" not in payment:
        payment["ref"] = provider_for(method).charge(total, details)
    order = Order(order_id=generate_order_id(db), buyer_id=buyer_id, subtotal=subtotal,
                  shipping_fee=shipping, total=total, status="awaiting_pickup", payment_method=method,
                  payment_ref=payment["ref"])
    db.add(order); db.flush()
    for entry, item, fee in lines:
        item.quantity -= entry.quantity
        if item.quantity == 0: item.status = "sold"
        db.add(OrderItem(order_id=order.id, listing_id=item.id, quantity=entry.quantity,
                         unit_price=to_money(item.price), item_shipping_fee=fee * entry.quantity))
        db.delete(entry)
    rate = as_decimal(settings.commission_rate)
    db.add(Commission(order_id=order.id, amount=to_money(subtotal * rate), rate=rate))
    try:
        db.commit(); db.refresh(order)
    except Exception:
        db.rollback(); raise
    return order

def checkout(db: Session, buyer_id: int, method: str, details: str) -> Order:
    """Retry a rare concurrent unique-ID collision after rolling back the transaction.

    Validation or payment failures roll back too, which releases the stock row locks immediately.
    """
    payment: dict = {}
    for attempt in range(5):
        try:
            return _checkout_once(db, buyer_id, method, details, payment)
        except IntegrityError as exc:
            db.rollback()
            if "order_id" not in str(exc).lower() or attempt == 4:
                raise
        except ValueError:
            db.rollback()
            raise
    raise RuntimeError("Could not allocate a unique order ID")
