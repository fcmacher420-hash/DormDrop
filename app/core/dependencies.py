from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User

bearer = HTTPBearer(auto_error=False)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    user = db.get(User, user_id)
    if not user or user.is_suspended:
        raise HTTPException(401, "Account unavailable")
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user

def seller_user(user: User = Depends(current_user)) -> User:
    if user.account_type != "seller" or not user.is_seller or not user.is_verified:
        raise HTTPException(403, "Approved, verified seller access required")
    return user

def buyer_user(user: User = Depends(current_user)) -> User:
    if user.account_type != "buyer":
        raise HTTPException(403, "This action is available to buyer accounts only")
    return user
