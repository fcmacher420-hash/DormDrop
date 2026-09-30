from datetime import datetime, timezone
from app.models import CartItem, Commission, Listing, Order, User
from app.services.orders import checkout, generate_order_id

class FixedRandom:
    def __init__(self, values): self.values = iter(values)
    def randint(self, _low, _high): return next(self.values)

def test_order_id_format_and_collision_retry(db):
    buyer = User(email="buyer@campus.edu", password_hash="x", campus="Campus", dorm="Hall")
    db.add(buyer); db.flush()
    db.add(Order(order_id="DD-20260102-0007", buyer_id=buyer.id, subtotal=0, shipping_fee=0,
                 total=0, status="awaiting_pickup", payment_method="visa", payment_ref="test"))
    db.commit()
    generated = generate_order_id(db, datetime(2026, 1, 2, tzinfo=timezone.utc), FixedRandom([7, 8]))
    assert generated == "DD-20260102-0008"

def test_checkout_commits_order_stock_cart_and_commission_atomically(db):
    buyer = User(email="buyer@campus.edu", password_hash="x", campus="Campus", dorm="Hall", is_verified=True)
    seller = User(email="seller@campus.edu", password_hash="x", campus="Campus", dorm="Hall", is_verified=True, is_seller=True)
    db.add_all([buyer, seller]); db.flush()
    listing = Listing(seller_id=seller.id, title="Book", description="Used book", category="Books", price=100,
                      length_cm=10, width_cm=10, height_cm=10, weight_kg=1, quantity=3, status="approved")
    db.add(listing); db.flush()
    cart_item = CartItem(buyer_id=buyer.id, listing_id=listing.id, quantity=2)
    db.add(cart_item); db.commit()

    order = checkout(db, buyer.id, "visa", "4242424242424242")

    assert order.order_id.startswith("DD-")
    assert order.status == "awaiting_pickup"
    assert order.subtotal == 200
    assert order.shipping_fee == 6  # 3 ZMW per item × quantity two.
    assert order.total == 206
    assert db.get(Listing, listing.id).quantity == 1
    assert db.query(CartItem).filter_by(buyer_id=buyer.id).count() == 0
    commission = db.query(Commission).filter_by(order_id=order.id).one()
    assert commission.amount == 20
