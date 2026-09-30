from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import current_user, seller_user, admin_user
from app.models import Listing, ListingImage, OrderItem, User
from app.schemas.schemas import ListingIn

router = APIRouter(tags=["listings"])

def output(item: Listing):
    return {"id": item.id, "seller_id": item.seller_id, "title": item.title, "description": item.description,
            "category": item.category, "price": item.price, "length_cm": item.length_cm, "width_cm": item.width_cm,
            "height_cm": item.height_cm, "weight_kg": item.weight_kg, "quantity": item.quantity,
            "status": item.status, "created_at": item.created_at,
            "images": [{"id": image.id, "url": image.url} for image in item.images]}

def apply_payload(item: Listing, payload: ListingIn, db: Session, reset_approval: bool):
    for key in ("title", "description", "category", "price", "length_cm", "width_cm", "height_cm", "weight_kg", "quantity"):
        setattr(item, key, getattr(payload, key))
    if reset_approval:
        item.status = "pending_approval"
    item.images.clear()
    item.images.extend(ListingImage(url=url) for url in payload.images)
    db.commit()
    db.refresh(item)

@router.get("/listings")
def browse(category: str | None = None, min_price: float | None = None, max_price: float | None = None,
          max_weight: float | None = None, max_length_cm: float | None = None,
          max_width_cm: float | None = None, max_height_cm: float | None = None,
          campus: str | None = None, dorm: str | None = None,
          db: Session = Depends(get_db)):
    query = select(Listing).join(User, Listing.seller_id == User.id).where(Listing.status == "approved", Listing.quantity > 0)
    if category: query = query.where(Listing.category == category)
    if min_price is not None: query = query.where(Listing.price >= min_price)
    if max_price is not None: query = query.where(Listing.price <= max_price)
    if max_weight is not None: query = query.where(Listing.weight_kg <= max_weight)
    if max_length_cm is not None: query = query.where(Listing.length_cm <= max_length_cm)
    if max_width_cm is not None: query = query.where(Listing.width_cm <= max_width_cm)
    if max_height_cm is not None: query = query.where(Listing.height_cm <= max_height_cm)
    if campus: query = query.where(User.campus.ilike(f"%{campus}%"))
    if dorm: query = query.where(User.dorm.ilike(f"%{dorm}%"))
    return [output(item) for item in db.scalars(query.order_by(Listing.created_at.desc()))]

@router.get("/listings/{listing_id}")
def detail(listing_id: int, db: Session = Depends(get_db)):
    item = db.get(Listing, listing_id)
    if not item or item.status != "approved":
        raise HTTPException(404, "Listing not found")
    data = output(item)
    seller = db.get(User, item.seller_id)
    data["seller"] = {"id": seller.id, "email": seller.email, "campus": seller.campus,
                      "dorm": seller.dorm, "rating_avg": seller.rating_avg}
    return data

@router.post("/listings", status_code=201)
def create(payload: ListingIn, db: Session = Depends(get_db), user: User = Depends(seller_user)):
    item = Listing(seller_id=user.id, **payload.model_dump(exclude={"images"}))
    item.images = [ListingImage(url=url) for url in payload.images]
    db.add(item)
    db.commit()
    db.refresh(item)
    return output(item)

@router.put("/listings/{listing_id}")
def update(listing_id: int, payload: ListingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    if not user.is_admin and item.seller_id != user.id: raise HTTPException(403, "Not your listing")
    apply_payload(item, payload, db, reset_approval=not user.is_admin)
    return output(item)

@router.delete("/listings/{listing_id}", status_code=204)
def delete(listing_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    if not user.is_admin and item.seller_id != user.id: raise HTTPException(403, "Not your listing")
    if db.scalar(select(OrderItem.id).where(OrderItem.listing_id == item.id)):
        raise HTTPException(409, "A listing in an order cannot be deleted; mark it sold instead")
    db.delete(item)
    db.commit()

@router.post("/listings/{listing_id}/sold")
def mark_sold(listing_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    if not user.is_admin and item.seller_id != user.id: raise HTTPException(403, "Not your listing")
    item.quantity = 0
    item.status = "sold"
    db.commit()
    return output(item)

@router.get("/admin/listings/pending")
def pending(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [output(item) for item in db.scalars(select(Listing).where(Listing.status == "pending_approval"))]

@router.get("/admin/listings")
def all_listings(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [output(item) for item in db.scalars(select(Listing).order_by(Listing.created_at.desc()))]

@router.post("/admin/listings/{listing_id}/approve")
def approve(listing_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    item.status = "approved"
    db.commit()
    return output(item)

@router.post("/admin/listings/{listing_id}/disapprove")
def disapprove(listing_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    item.status = "disapproved"
    db.commit()
    return output(item)

@router.put("/admin/listings/{listing_id}")
def admin_edit(listing_id: int, payload: ListingIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    item = db.get(Listing, listing_id)
    if not item: raise HTTPException(404, "Listing not found")
    apply_payload(item, payload, db, reset_approval=False)
    return output(item)
