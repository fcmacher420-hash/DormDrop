from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import current_user, admin_user, buyer_user, seller_user
from app.core.money import to_money
from app.models import CartItem, Commission, Listing, Message, Order, OrderItem, Review, SellerPayout, SellerRequest, User
from app.schemas.schemas import CartAddIn, CartUpdateIn, CheckoutIn, MessageIn, PayoutIn, ReviewIn, StatusIn
from app.services import earnings
from app.services.orders import checkout
from app.services.shipping import shipping_fee

router = APIRouter(tags=["marketplace"])

ORDER_TRANSITIONS = {"awaiting_pickup": "picked_up", "picked_up": "in_transit", "in_transit": "delivered"}


# ---------------------------------------------------------------- orders

def order_seller_ids(db: Session, order: Order) -> set[int]:
    """Distinct sellers whose listings appear in the order."""
    query = select(Listing.seller_id).join(OrderItem, OrderItem.listing_id == Listing.id).where(OrderItem.order_id == order.id)
    return set(db.scalars(query).all())

def order_data(order: Order, db: Session, viewer: User | None = None):
    """Serialise an order. Payment details are only shown to the buyer and admins."""
    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    item_rows = []
    for line in lines:
        listing = db.get(Listing, line.listing_id)
        item_rows.append({"listing_id": line.listing_id, "seller_id": listing.seller_id if listing else None,
                          "quantity": line.quantity, "unit_price": line.unit_price,
                          "item_shipping_fee": line.item_shipping_fee})
    data = {"id": order.id, "order_id": order.order_id, "buyer_id": order.buyer_id,
            "subtotal": order.subtotal, "shipping_fee": order.shipping_fee, "total": order.total,
            "status": order.status, "created_at": order.created_at, "items": item_rows,
            "reviewed_seller_ids": db.scalars(select(Review.seller_id).where(Review.order_id == order.id)).all()}
    if viewer is None or viewer.is_admin or viewer.id == order.buyer_id:
        data["payment_method"] = order.payment_method
        data["payment_ref"] = order.payment_ref
    return data


# ---------------------------------------------------------------- cart

@router.get("/cart")
def get_cart(db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    entries = db.scalars(select(CartItem).where(CartItem.buyer_id == user.id)).all()
    rows = []
    for entry in entries:
        item = db.get(Listing, entry.listing_id)
        if item is None: continue
        fee = shipping_fee(item.length_cm, item.width_cm, item.height_cm, item.weight_kg)
        rows.append({"id": entry.id, "listing_id": item.id, "title": item.title, "price": item.price,
                     "quantity": entry.quantity, "available_quantity": item.quantity,
                     "item_subtotal": to_money(item.price) * entry.quantity,
                     "item_shipping_fee": fee * entry.quantity, "image": item.images[0].url if item.images else ""})
    subtotal = sum((x["item_subtotal"] for x in rows), to_money(0))
    ship = sum((x["item_shipping_fee"] for x in rows), to_money(0))
    return {"items": rows, "subtotal": subtotal, "shipping_fee": ship, "grand_total": subtotal + ship,
            "currency": settings.currency}

@router.post("/cart/items", status_code=201)
def add_cart(payload: CartAddIn, db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    item = db.get(Listing, payload.listing_id)
    if not item or item.status != "approved": raise HTTPException(404, "Listing not available")
    if item.seller_id == user.id: raise HTTPException(400, "You cannot add your own listing")
    existing = db.scalar(select(CartItem).where(CartItem.buyer_id == user.id, CartItem.listing_id == item.id))
    quantity = payload.quantity + (existing.quantity if existing else 0)
    if quantity > item.quantity: raise HTTPException(409, "Requested quantity is not in stock")
    if existing: existing.quantity = quantity
    else: db.add(CartItem(buyer_id=user.id, listing_id=item.id, quantity=payload.quantity))
    db.commit()
    return {"message": "Added to cart"}

@router.put("/cart/items/{item_id}")
def update_cart(item_id: int, payload: CartUpdateIn, db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    entry = db.get(CartItem, item_id)
    if not entry or entry.buyer_id != user.id: raise HTTPException(404, "Cart item not found")
    listing = db.get(Listing, entry.listing_id)
    if listing is None or listing.status != "approved": raise HTTPException(404, "Listing not available")
    if payload.quantity > listing.quantity: raise HTTPException(409, "Requested quantity is not in stock")
    entry.quantity = payload.quantity; db.commit()
    return {"message": "Cart updated"}

@router.delete("/cart/items/{item_id}", status_code=204)
def remove_cart(item_id: int, db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    entry = db.get(CartItem, item_id)
    if not entry or entry.buyer_id != user.id: raise HTTPException(404, "Cart item not found")
    db.delete(entry); db.commit()

@router.post("/checkout", status_code=201)
def place_order(payload: CheckoutIn, db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    try:
        order = checkout(db, user.id, payload.payment_method, payload.payment_details)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return order_data(order, db, user)


# ---------------------------------------------------------------- orders and fulfilment

@router.get("/orders")
def my_orders(db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    orders = db.scalars(select(Order).where(Order.buyer_id == user.id).order_by(Order.created_at.desc())).all()
    return [order_data(order, db, user) for order in orders]

@router.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.scalar(select(Order).where(Order.order_id == order_id))
    if not order: raise HTTPException(404, "Order not found")
    if not user.is_admin and order.buyer_id != user.id and user.id not in order_seller_ids(db, order):
        raise HTTPException(403, "Order access denied")
    return order_data(order, db, user)

@router.put("/admin/orders/{order_id}/status")
def set_order_status(order_id: str, payload: StatusIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Admins may advance any order. A seller may advance an order only when every item in it is theirs,
    because status is tracked per order and must not be controlled by one seller of several."""
    order = db.scalar(select(Order).where(Order.order_id == order_id))
    if not order: raise HTTPException(404, "Order not found")
    if not user.is_admin:
        sellers = order_seller_ids(db, order)
        if user.account_type != "seller" or not user.is_seller or not user.is_verified or sellers != {user.id}:
            raise HTTPException(403, "Only an admin can update orders that include other sellers' items")
    if ORDER_TRANSITIONS.get(order.status) != payload.status: raise HTTPException(409, "Invalid order status transition")
    order.status = payload.status; db.commit()
    return order_data(order, db, user)

@router.get("/admin/orders")
def all_orders(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return [order_data(x, db, admin) for x in db.scalars(select(Order).order_by(Order.created_at.desc()))]


# ---------------------------------------------------------------- commissions and payouts

@router.get("/admin/commissions")
def commissions(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    entries = db.execute(select(Commission, Order.order_id).join(Order, Commission.order_id == Order.id).order_by(Commission.created_at.desc())).all()
    payouts = db.scalars(select(SellerPayout).order_by(SellerPayout.created_at.desc())).all()
    return {"currency": settings.currency, "commission_rate": settings.commission_rate,
            "total_earnings": sum((x[0].amount for x in entries), to_money(0)),
            "entries": [{"id": c.id, "order_id": public_id, "amount": c.amount, "rate": c.rate, "created_at": c.created_at} for c, public_id in entries],
            "payouts": [{"id": p.id, "seller_id": p.seller_id, "amount": p.amount, "reference": p.reference, "created_at": p.created_at} for p in payouts]}

@router.post("/admin/payouts", status_code=201)
def record_payout(payload: PayoutIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    seller = db.get(User, payload.seller_id)
    if not seller or not seller.is_seller: raise HTTPException(404, "Seller not found")
    amount = to_money(payload.amount)
    available = earnings.summary(db, seller.id)["available_for_payout"]
    if amount > available:
        raise HTTPException(409, f"Payout exceeds the {settings.currency} {available} available (delivered orders, after commission, minus earlier payouts)")
    payout = SellerPayout(seller_id=seller.id, amount=amount, reference=payload.reference, processed_by=admin.id)
    db.add(payout); db.commit(); db.refresh(payout)
    return {"id": payout.id, "seller_id": payout.seller_id, "amount": payout.amount, "reference": payout.reference}


# ---------------------------------------------------------------- seller onboarding

@router.get("/partners")
def public_partners(db: Session = Depends(get_db)):
    """Show verified seller accounts in the public partner directory."""
    sellers = db.scalars(select(User).where(User.account_type == "seller", User.is_verified.is_(True))
                         .order_by(User.created_at.desc(), User.id.desc())).all()
    return [{"business_name": seller.business_name or seller.email.partition("@")[0].replace(".", " ").replace("-", " ").title(),
             "contact_person": seller.contact_person,
             "email": seller.email, "phone": seller.phone, "country": seller.country,
             "business_description": seller.business_description, "product_types": seller.product_types,
             "status": "Approved partner" if seller.is_seller else "Registered supplier"}
            for seller in sellers]

@router.post("/seller-requests", status_code=201)
def request_seller(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.is_verified: raise HTTPException(403, "Verify your email first")
    if user.account_type != "seller": raise HTTPException(403, "Only seller accounts can request seller approval")
    if user.is_seller: raise HTTPException(409, "You are already an approved seller")
    pending = db.scalar(select(SellerRequest).where(SellerRequest.user_id == user.id, SellerRequest.status == "pending"))
    if pending: raise HTTPException(409, "Seller request is already pending")
    request = SellerRequest(user_id=user.id); db.add(request); db.commit(); db.refresh(request)
    return {"id": request.id, "status": request.status}

@router.get("/admin/seller-requests")
def seller_requests(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    rows = db.execute(select(SellerRequest, User.email).join(User, SellerRequest.user_id == User.id).order_by(SellerRequest.id)).all()
    return [{"id": r.id, "user_id": r.user_id, "email": email, "status": r.status,
             "country": db.get(User, r.user_id).country, "business_name": db.get(User, r.user_id).business_name,
             "contact_person": db.get(User, r.user_id).contact_person, "phone": db.get(User, r.user_id).phone,
             "business_description": db.get(User, r.user_id).business_description,
             "product_types": db.get(User, r.user_id).product_types} for r, email in rows]

@router.post("/admin/seller-requests/{request_id}/approve")
def approve_seller(request_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    request = db.get(SellerRequest, request_id)
    if not request or request.status != "pending": raise HTTPException(404, "Pending request not found")
    request.status = "approved"; request.reviewed_by = admin.id; request.reviewed_at = datetime.now(timezone.utc)
    db.get(User, request.user_id).is_seller = True; db.commit()
    return {"id": request.id, "status": request.status}

@router.post("/admin/seller-requests/{request_id}/reject")
def reject_seller(request_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    request = db.get(SellerRequest, request_id)
    if not request or request.status != "pending": raise HTTPException(404, "Pending request not found")
    request.status = "rejected"; request.reviewed_by = admin.id; request.reviewed_at = datetime.now(timezone.utc); db.commit()
    return {"id": request.id, "status": request.status}


# ---------------------------------------------------------------- user administration

@router.get("/admin/users")
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [{"id": x.id, "email": x.email, "campus": x.campus, "dorm": x.dorm, "is_verified": x.is_verified,
             "account_type": x.account_type, "country": x.country, "business_name": x.business_name,
             "contact_person": x.contact_person, "phone": x.phone,
             "business_description": x.business_description, "product_types": x.product_types,
             "is_seller": x.is_seller, "is_admin": x.is_admin, "is_suspended": x.is_suspended}
            for x in db.scalars(select(User).order_by(User.id))]

@router.post("/admin/users/{user_id}/suspend")
def suspend(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    target = db.get(User, user_id)
    if not target: raise HTTPException(404, "User not found")
    if target.id == admin.id: raise HTTPException(400, "Admin cannot suspend their own account")
    target.is_suspended = True; db.commit(); return {"message": "User suspended"}

@router.post("/admin/users/{user_id}/unsuspend")
def unsuspend(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    target = db.get(User, user_id)
    if not target: raise HTTPException(404, "User not found")
    target.is_suspended = False; db.commit(); return {"message": "User unsuspended"}


# ---------------------------------------------------------------- seller dashboard

@router.get("/seller/dashboard")
def seller_dashboard(db: Session = Depends(get_db), user: User = Depends(seller_user)):
    listings = db.scalars(select(Listing).where(Listing.seller_id == user.id)).all()
    totals = earnings.summary(db, user.id)
    sole = earnings.sole_seller_orders(db, sorted({s["order_pk"] for s in totals["sales"]}))
    sales = [{"order_id": s["order_id"], "listing_id": s["listing_id"], "quantity": s["quantity"], "gross": s["gross"],
              "net": s["net"], "status": s["status"], "can_advance": s["order_pk"] in sole} for s in totals["sales"]]
    return {"listings": [{"id": x.id, "title": x.title, "description": x.description, "category": x.category,
                          "price": x.price, "length_cm": x.length_cm, "width_cm": x.width_cm,
                          "height_cm": x.height_cm, "weight_kg": x.weight_kg,
                          "images": [image.url for image in x.images], "quantity": x.quantity, "status": x.status} for x in listings],
            "sales": sales, "gross_sales": totals["gross_sales"],
            "revenue_after_commission": totals["revenue_after_commission"],
            "available_for_payout": totals["available_for_payout"], "paid_out": totals["paid_out"],
            "commission_rate": settings.commission_rate, "currency": settings.currency}

@router.get("/seller/admin-contact")
def seller_admin_contact(db: Session = Depends(get_db), user: User = Depends(seller_user)):
    admin = db.scalar(select(User).where(User.is_admin.is_(True)).order_by(User.id))
    if not admin: raise HTTPException(404, "Admin account not configured")
    return {"id": admin.id, "email": admin.email}


# ---------------------------------------------------------------- reviews

@router.post("/reviews", status_code=201)
def create_review(payload: ReviewIn, db: Session = Depends(get_db), user: User = Depends(buyer_user)):
    order = db.scalar(select(Order).where(Order.order_id == payload.order_id, Order.buyer_id == user.id))
    if not order: raise HTTPException(404, "Order not found")
    if order.status != "delivered": raise HTTPException(409, "Reviews are available after delivery")
    seller_ids = order_seller_ids(db, order)
    if payload.seller_id is not None:
        seller_id = payload.seller_id
        if seller_id not in seller_ids: raise HTTPException(400, "Seller is not part of this order")
    elif len(seller_ids) == 1:
        seller_id = next(iter(seller_ids))
    else:
        raise HTTPException(400, "Choose a seller from this order")
    if db.scalar(select(Review).where(Review.order_id == order.id, Review.seller_id == seller_id)):
        raise HTTPException(409, "This seller has already been reviewed for the order")
    review = Review(order_id=order.id, buyer_id=user.id, seller_id=seller_id, rating=payload.rating, comment=payload.comment)
    db.add(review); db.flush()
    seller = db.get(User, seller_id)
    seller.rating_avg = float(db.scalar(select(func.avg(Review.rating)).where(Review.seller_id == seller_id)) or 0)
    db.commit()
    return {"id": review.id, "seller_id": seller_id, "rating": review.rating, "comment": review.comment}

@router.get("/sellers/{seller_id}/reviews")
def seller_reviews(seller_id: int, db: Session = Depends(get_db)):
    """Public endpoint: reviewers are anonymous so buyer emails are never exposed."""
    rows = db.scalars(select(Review).where(Review.seller_id == seller_id).order_by(Review.created_at.desc())).all()
    return [{"rating": r.rating, "comment": r.comment, "buyer": "Verified buyer", "created_at": r.created_at} for r in rows]


# ---------------------------------------------------------------- chat

def has_conversation(db: Session, first_id: int, second_id: int) -> bool:
    """True once the two users have exchanged at least one message (replies then need no listing/order context)."""
    found = db.scalar(select(Message.id).where(
        ((Message.sender_id == first_id) & (Message.receiver_id == second_id)) |
        ((Message.sender_id == second_id) & (Message.receiver_id == first_id))).limit(1))
    return found is not None

def can_chat(sender: User, receiver: User, listing_id: int | None, order_id: str | None, db: Session) -> bool:
    if sender.is_admin or receiver.is_admin:
        return (sender.is_admin and receiver.is_seller) or (receiver.is_admin and sender.is_seller)
    if order_id:
        order = db.scalar(select(Order).where(Order.order_id == order_id))
        if not order: return False
        sellers = order_seller_ids(db, order)
        return (sender.id == order.buyer_id and receiver.id in sellers) or (receiver.id == order.buyer_id and sender.id in sellers)
    if listing_id:
        listing = db.get(Listing, listing_id)
        return listing is not None and listing.seller_id in {sender.id, receiver.id}
    return False

def _peer_label(peer: User) -> str:
    role = "Admin" if peer.is_admin else "Seller" if peer.account_type == "seller" else "Buyer"
    return f"{role} #{peer.id} · {peer.dorm}"

@router.get("/messages")
def conversations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Inbox: one entry per conversation partner, newest first, so sellers can find and answer buyers."""
    rows = db.scalars(select(Message).where((Message.sender_id == user.id) | (Message.receiver_id == user.id))
                      .order_by(Message.created_at.desc(), Message.id.desc())).all()
    latest: dict[int, Message] = {}
    for message in rows:
        peer_id = message.receiver_id if message.sender_id == user.id else message.sender_id
        latest.setdefault(peer_id, message)
    peers = {p.id: p for p in db.scalars(select(User).where(User.id.in_(list(latest))))} if latest else {}
    return [{"peer_id": peer_id, "peer_label": _peer_label(peers[peer_id]), "last_message": message.body[:120],
             "last_at": message.created_at} for peer_id, message in latest.items() if peer_id in peers]

@router.get("/messages/{user_id}")
def get_messages(user_id: int, listing_id: int | None = None, order_id: str | None = None,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Messages with one partner. Allowed when a listing/order/admin-seller link exists or a thread already exists.
    A first-time contextual chat returns an empty list instead of an error."""
    if user.id == user_id: raise HTTPException(400, "Choose a conversation partner")
    peer = db.get(User, user_id)
    if not peer or not (can_chat(user, peer, listing_id, order_id, db) or has_conversation(db, user.id, peer.id)):
        raise HTTPException(403, "Chat access denied")
    rows = db.scalars(select(Message).where(((Message.sender_id == user.id) & (Message.receiver_id == peer.id)) |
                                            ((Message.sender_id == peer.id) & (Message.receiver_id == user.id)))
                      .order_by(Message.created_at, Message.id)).all()
    return [{"id": x.id, "sender_id": x.sender_id, "receiver_id": x.receiver_id, "listing_id": x.listing_id,
             "order_id": db.get(Order, x.order_id).order_id if x.order_id else None, "body": x.body,
             "created_at": x.created_at} for x in rows]

@router.post("/messages", status_code=201)
def send_message(payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = db.get(User, payload.receiver_id)
    if not peer: raise HTTPException(404, "Recipient not found")
    if peer.id == user.id: raise HTTPException(400, "You cannot message yourself")
    if not (can_chat(user, peer, payload.listing_id, payload.order_id, db) or has_conversation(db, user.id, peer.id)):
        raise HTTPException(403, "Chat access denied")
    internal_order_id = None
    if payload.order_id:
        order = db.scalar(select(Order).where(Order.order_id == payload.order_id))
        if order: internal_order_id = order.id
    # Ignore a listing id that does not exist rather than failing on the foreign key.
    listing_id = payload.listing_id if payload.listing_id and db.get(Listing, payload.listing_id) else None
    message = Message(sender_id=user.id, receiver_id=peer.id, listing_id=listing_id,
                      order_id=internal_order_id, body=payload.body)
    db.add(message); db.commit(); db.refresh(message)
    return {"id": message.id, "sender_id": message.sender_id, "receiver_id": message.receiver_id,
            "body": message.body, "created_at": message.created_at}
