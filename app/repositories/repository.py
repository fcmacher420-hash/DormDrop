from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import User, Listing, CartItem, Order, SellerRequest, Message, Review

class Repository:
    """Persistence boundary used by business services."""
    def __init__(self, db: Session): self.db = db
    def user_by_email(self, email: str): return self.db.scalar(select(User).where(User.email == email.lower()))
    def user(self, user_id: int): return self.db.get(User, user_id)
    def listing(self, listing_id: int): return self.db.get(Listing, listing_id)
    def cart(self, buyer_id: int): return list(self.db.scalars(select(CartItem).where(CartItem.buyer_id == buyer_id)))
    def order_by_public_id(self, public_id: str): return self.db.scalar(select(Order).where(Order.order_id == public_id))
    def seller_request(self, request_id: int): return self.db.get(SellerRequest, request_id)
    def message(self, message_id: int): return self.db.get(Message, message_id)
    def review(self, order_id: int): return self.db.scalar(select(Review).where(Review.order_id == order_id))
