from sqlalchemy import select
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Listing, ListingImage, User

def seed():
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
        if not admin:
            admin = User(email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password),
                         campus="DormDrop", dorm="Admin", is_verified=True, is_admin=True)
            db.add(admin)
        seller = db.scalar(select(User).where(User.email == "seller@demo.edu"))
        if not seller:
            seller = User(email="seller@demo.edu", password_hash=hash_password("SellerDemo123!"),
                          campus="University of Zambia", dorm="Kwacha Hall", is_verified=True, is_seller=True)
            db.add(seller)
            db.flush()
            sample = Listing(seller_id=seller.id, title="Desk lamp", description="Adjustable LED desk lamp in good condition.",
                             category="Home", price=150, length_cm=25, width_cm=15, height_cm=12,
                             weight_kg=0.7, quantity=2, status="approved")
            sample.images = [ListingImage(url="https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=700")]
            db.add(sample)
        db.commit()
        print(f"Seeded admin {settings.admin_email} and demo seller seller@demo.edu")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
