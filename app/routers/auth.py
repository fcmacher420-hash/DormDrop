from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, new_token, verify_password
from app.core.dependencies import current_user
from app.models import User
from app.schemas.schemas import LoginIn, SignupIn, VerifyIn

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", status_code=201)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if payload.account_type == "buyer":
        domain = email.rsplit("@", 1)[-1]
        allowed_domains = tuple(suffix.lower().lstrip(".@") for suffix in settings.email_suffixes)
        if not any(domain == allowed or domain.endswith("." + allowed) for allowed in allowed_domains):
            raise HTTPException(422, f"Use an email ending in {', '.join(settings.email_suffixes)}")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email is already registered")
    token = new_token()
    user = User(email=email, password_hash=hash_password(payload.password),
                campus=payload.campus or payload.country, dorm=payload.dorm or payload.business_name,
                account_type=payload.account_type, country=payload.country, business_name=payload.business_name,
                contact_person=payload.contact_person, phone=payload.phone,
                business_description=payload.business_description, product_types=payload.product_types,
                verification_token=token)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two signups raced past the existence check above
        db.rollback()
        raise HTTPException(409, "Email is already registered")
    return {"message": "Account created. Verify using the development token.",
            "account_type": payload.account_type, "verification_token": token}

@router.post("/verification-token")
def refresh_verification_token(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if user.is_verified:
        raise HTTPException(409, "Email is already verified. Please sign in.")
    user.verification_token = new_token()
    db.commit()
    return {"message": "A fresh development verification token is ready.",
            "verification_token": user.verification_token}

@router.post("/verify")
def verify(payload: VerifyIn, db: Session = Depends(get_db)):
    submitted_token = payload.token.strip()
    user = db.query(User).filter_by(verification_token=submitted_token).first()
    if not user:
        raise HTTPException(400, "Invalid verification token")
    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email verified"}

@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if user.is_suspended:
        raise HTTPException(403, "Account suspended")
    if not user.is_verified:
        raise HTTPException(403, "Verify your email before signing in")
    return {"access_token": create_access_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "account_type": user.account_type,
                     "is_seller": user.is_seller, "is_admin": user.is_admin}}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "campus": user.campus, "dorm": user.dorm,
            "country": user.country, "business_name": user.business_name, "account_type": user.account_type,
            "contact_person": user.contact_person, "phone": user.phone,
            "business_description": user.business_description, "product_types": user.product_types,
            "is_verified": user.is_verified, "is_seller": user.is_seller, "is_admin": user.is_admin}
