from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, new_token, verify_password
from app.core.dependencies import current_user
from app.models import User
from app.schemas.schemas import LoginIn, SignupIn, VerifyIn

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", status_code=201)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if not email.endswith(".edu"):
        raise HTTPException(422, "Use a university .edu email address")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email is already registered")
    token = new_token()
    user = User(email=email, password_hash=hash_password(payload.password), campus=payload.campus,
                dorm=payload.dorm, verification_token=token)
    db.add(user)
    db.commit()
    return {"message": "Account created. Verify using the development token.", "verification_token": token}

@router.post("/verify")
def verify(payload: VerifyIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(verification_token=payload.token).first()
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
        raise HTTPException(403, "Verify your .edu email before signing in")
    return {"access_token": create_access_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "is_seller": user.is_seller, "is_admin": user.is_admin}}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "campus": user.campus, "dorm": user.dorm,
            "is_verified": user.is_verified, "is_seller": user.is_seller, "is_admin": user.is_admin}
