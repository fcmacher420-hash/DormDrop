from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import current_user, admin_user
from app.models import CartItem, Commission, Listing, Message, Order, OrderItem, Review, SellerPayout, SellerRequest, User
from app.schemas.schemas import CartAddIn, CartUpdateIn, CheckoutIn, MessageIn, PayoutIn, ReviewIn, StatusIn
from app.services.orders import checkout
from app.services.shipping import shipping_fee

router = APIRouter(tags=["marketplace"])

def order_data(order: Order, db: Session):
    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    item_rows = []
    for line in lines:
        listing = db.get(Listing, line.listing_id)
        item_rows.append({"listing_id": line.listing_id, "seller_id": listing.seller_id if listing else None,
                          "quantity": line.quantity, "unit_price": line.unit_price,
                          "item_shipping_fee": line.item_shipping_fee})
    return {"id": order.id, "order_id": order.order_id, "buyer_id": order.buyer_id,
            "subtotal": order.subtotal, "shipping_fee": order.shipping_fee, "total": order.total,
            "status": order.status, "payment_method": order.payment_method,
            "payment_ref": order.payment_ref, "created_at": order.created_at,
            "items": item_rows}

@router.get("/cart")
def get_cart(db: Session = Depends(get_db), user: User = Depends(current_user)):
    entries = db.scalars(select(CartItem).where(CartItem.buyer_id == user.id)).all()
    rows = []
    for entry in entries:
        item = db.get(Listing, entry.listing_id)
        if item is None: continue
        fee = shipping_fee(item.length_cm, item.width_cm, item.height_cm, item.weight_kg)
        rows.append({"id": entry.id, "listing_id": item.id, "title": item.title, "price": item.price,
                     "quantity": entry.quantity, "available_quantity": item.quantity, "item_subtotal": round(item.price*entry.quantity,2),
                     "item_shipping_fee": round(fee*entry.quantity,2), "image": item.images[0].url if item.images else ""})
    subtotal = round(sum(x["item_subtotal"] for x in rows), 2)
    ship = round(sum(x["item_shipping_fee"] for x in rows), 2)
    return {"items": rows, "subtotal": subtotal, "shipping_fee": ship, "grand_total": round(subtotal+ship,2), "currency": settings.currency}

@router.post("/cart/items", status_code=201)
def add_cart(payload: CartAddIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
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
def update_cart(item_id: int, payload: CartUpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    entry = db.get(CartItem, item_id)
    if not entry or entry.buyer_id != user.id: raise HTTPException(404, "Cart item not found")
    listing = db.get(Listing, entry.listing_id)
    if payload.quantity > listing.quantity: raise HTTPException(409, "Requested quantity is not in stock")
    entry.quantity = payload.quantity; db.commit()
    return {"message": "Cart updated"}

@router.delete("/cart/items/{item_id}", status_code=204)
def remove_cart(item_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    entry = db.get(CartItem, item_id)
    if not entry or entry.buyer_id != user.id: raise HTTPException(404, "Cart item not found")
    db.delete(entry); db.commit()

@router.post("/checkout", status_code=201)
def place_order(payload: CheckoutIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        order = checkout(db, user.id, payload.payment_method, payload.payment_details)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return order_data(order, db)

@router.get("/orders")
def my_orders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    orders = db.scalars(select(Order).where(Order.buyer_id == user.id).order_by(Order.created_at.desc())).all()
    return [order_data(order, db) for order in orders]

@router.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.scalar(select(Order).where(Order.order_id == order_id))
    if not order: raise HTTPException(404, "Order not found")
    if not user.is_admin and order.buyer_id != user.id:
        item_ids = db.scalars(select(OrderItem.listing_id).where(OrderItem.order_id == order.id)).all()
        sellers = db.scalars(select(Listing.seller_id).where(Listing.id.in_(item_ids))).all()
        if user.id not in sellers: raise HTTPException(403, "Order access denied")
    return order_data(order, db)

@router.put("/admin/orders/{order_id}/status")
def set_order_status(order_id: str, payload: StatusIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.scalar(select(Order).where(Order.order_id == order_id))
    if not order: raise HTTPException(404, "Order not found")
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    seller_ids = {db.get(Listing, x.listing_id).seller_id for x in items if db.get(Listing, x.listing_id)}
    if not user.is_admin and (not user.is_seller or user.id not in seller_ids): raise HTTPException(403, "Order update denied")
    allowed = {"awaiting_pickup": "picked_up", "picked_up": "in_transit", "in_transit": "delivered"}
    if allowed.get(order.status) != payload.status: raise HTTPException(409, "Invalid order status transition")
    order.status = payload.status; db.commit()
    return order_data(order, db)

@router.get("/admin/orders")
def all_orders(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [order_data(x, db) for x in db.scalars(select(Order).order_by(Order.created_at.desc()))]

@router.get("/admin/commissions")
def commissions(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    entries = db.execute(select(Commission, Order.order_id).join(Order, Commission.order_id == Order.id).order_by(Commission.created_at.desc())).all()
    payouts = db.scalars(select(SellerPayout).order_by(SellerPayout.created_at.desc())).all()
    return {"currency": settings.currency, "commission_rate": settings.commission_rate,
            "total_earnings": round(sum(x[0].amount for x in entries), 2),
            "entries": [{"id": c.id, "order_id": public_id, "amount": c.amount, "rate": c.rate, "created_at": c.created_at} for c, public_id in entries],
            "payouts": [{"id": p.id, "seller_id": p.seller_id, "amount": p.amount, "reference": p.reference, "created_at": p.created_at} for p in payouts]}

@router.post("/admin/payouts", status_code=201)
def record_payout(payload: PayoutIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    seller = db.get(User, payload.seller_id)
    if not seller or not seller.is_seller: raise HTTPException(404, "Seller not found")
    payout = SellerPayout(seller_id=seller.id, amount=round(payload.amount, 2),
                          reference=payload.reference, processed_by=admin.id)
    db.add(payout); db.commit(); db.refresh(payout)
    return {"id": payout.id, "seller_id": payout.seller_id, "amount": payout.amount, "reference": payout.reference}

@router.post("/seller-requests", status_code=201)
def request_seller(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.is_verified: raise HTTPException(403, "Verify your .edu email first")
    if user.is_seller: raise HTTPException(409, "You are already an approved seller")
    pending = db.scalar(select(SellerRequest).where(SellerRequest.user_id == user.id, SellerRequest.status == "pending"))
    if pending: raise HTTPException(409, "Seller request is already pending")
    request = SellerRequest(user_id=user.id); db.add(request); db.commit(); db.refresh(request)
    return {"id": request.id, "status": request.status}

@router.get("/admin/seller-requests")
def seller_requests(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    rows = db.execute(select(SellerRequest, User.email).join(User, SellerRequest.user_id == User.id).order_by(SellerRequest.id)).all()
    return [{"id": r.id, "user_id": r.user_id, "email": email, "status": r.status} for r, email in rows]

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

@router.get("/admin/users")
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [{"id": x.id, "email": x.email, "campus": x.campus, "dorm": x.dorm, "is_verified": x.is_verified,
             "is_seller": x.is_seller, "is_suspended": x.is_suspended} for x in db.scalars(select(User).order_by(User.id))]

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

@router.get("/seller/dashboard")
def seller_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.is_seller: raise HTTPException(403, "Seller access required")
    listings = db.scalars(select(Listing).where(Listing.seller_id == user.id)).all()
    listing_ids = [x.id for x in listings]
    lines = db.scalars(select(OrderItem).where(OrderItem.listing_id.in_(listing_ids))).all() if listing_ids else []
    sales = [{"order_id": db.get(Order, line.order_id).order_id, "listing_id": line.listing_id,
              "quantity": line.quantity, "gross": line.unit_price * line.quantity,
              "status": db.get(Order, line.order_id).status} for line in lines]
    return {"listings": [{"id": x.id, "title": x.title, "description": x.description, "category": x.category,
                          "price": x.price, "length_cm": x.length_cm, "width_cm": x.width_cm,
                          "height_cm": x.height_cm, "weight_kg": x.weight_kg,
                          "images": [image.url for image in x.images], "quantity": x.quantity, "status": x.status} for x in listings],
            "sales": sales, "gross_sales": round(sum(x["gross"] for x in sales), 2),
            "revenue_after_commission": round(sum(x["gross"] for x in sales) * (1-settings.commission_rate), 2),
            "paid_out": round(db.scalar(select(func.sum(SellerPayout.amount)).where(SellerPayout.seller_id == user.id)) or 0, 2),
            "commission_rate": settings.commission_rate, "currency": settings.currency}

@router.get("/seller/admin-contact")
def seller_admin_contact(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.is_seller: raise HTTPException(403, "Seller access required")
    admin = db.scalar(select(User).where(User.is_admin.is_(True)).order_by(User.id))
    if not admin: raise HTTPException(404, "Admin account not configured")
    return {"id": admin.id, "email": admin.email}

@router.post("/reviews", status_code=201)
def create_review(payload: ReviewIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.scalar(select(Order).where(Order.order_id == payload.order_id, Order.buyer_id == user.id))
    if not order: raise HTTPException(404, "Order not found")
    if order.status != "delivered": raise HTTPException(409, "Reviews are available after delivery")
    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    seller_ids = {db.get(Listing, x.listing_id).seller_id for x in lines if db.get(Listing, x.listing_id)}
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
    rows = db.execute(select(Review, User.email).join(User, Review.buyer_id == User.id).where(Review.seller_id == seller_id).order_by(Review.created_at.desc())).all()
    return [{"rating": r.rating, "comment": r.comment, "buyer": email, "created_at": r.created_at} for r, email in rows]

def can_chat(sender: User, receiver: User, listing_id: int | None, order_id: str | None, db: Session) -> bool:
    if sender.is_admin or receiver.is_admin:
        return (sender.is_admin and receiver.is_seller) or (receiver.is_admin and sender.is_seller)
    if order_id:
        order = db.scalar(select(Order).where(Order.order_id == order_id))
        if not order: return False
        items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
        sellers = {db.get(Listing, x.listing_id).seller_id for x in items if db.get(Listing, x.listing_id)}
        return (sender.id == order.buyer_id and receiver.id in sellers) or (receiver.id == order.buyer_id and sender.id in sellers)
    if listing_id:
        listing = db.get(Listing, listing_id)
        return listing is not None and listing.seller_id in {sender.id, receiver.id} and not sender.is_admin and not receiver.is_admin
    return False

@router.get("/messages/{user_id}")
def get_messages(user_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.id == user_id: raise HTTPException(400, "Choose a conversation partner")
    peer = db.get(User, user_id)
    if not peer or not can_chat(user, peer, None, None, db):
        # Existing contextual messages grant access to the conversation.
        rows = db.scalars(select(Message).where(((Message.sender_id == user.id) & (Message.receiver_id == user_id)) |
                                                 ((Message.sender_id == user_id) & (Message.receiver_id == user.id))).order_by(Message.created_at)).all()
        if not peer or not rows: raise HTTPException(403, "Chat access denied")
    else:
        rows = db.scalars(select(Message).where(((Message.sender_id == user.id) & (Message.receiver_id == user_id)) |
                                                 ((Message.sender_id == user_id) & (Message.receiver_id == user.id))).order_by(Message.created_at)).all()
    return [{"id": x.id, "sender_id": x.sender_id, "receiver_id": x.receiver_id, "listing_id": x.listing_id,
             "order_id": db.get(Order, x.order_id).order_id if x.order_id else None, "body": x.body, "created_at": x.created_at} for x in rows]

@router.post("/messages", status_code=201)
def send_message(payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = db.get(User, payload.receiver_id)
    if not peer: raise HTTPException(404, "Recipient not found")
    if not can_chat(user, peer, payload.listing_id, payload.order_id, db): raise HTTPException(403, "Chat access denied")
    internal_order_id = None
    if payload.order_id:
        order = db.scalar(select(Order).where(Order.order_id == payload.order_id))
        if order: internal_order_id = order.id
    message = Message(sender_id=user.id, receiver_id=peer.id, listing_id=payload.listing_id,
                      order_id=internal_order_id, body=payload.body)
    db.add(message); db.commit(); db.refresh(message)
    return {"id": message.id, "sender_id": message.sender_id, "receiver_id": message.receiver_id,
            "body": message.body, "created_at": message.created_at}
