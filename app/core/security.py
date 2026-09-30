from datetime import datetime, timedelta, timezone
import secrets

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.secret_key, algorithm=settings.token_algorithm)


def decode_access_token(token: str) -> int:
    try:
        return int(jwt.decode(token, settings.secret_key, algorithms=[settings.token_algorithm])["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid or expired access token") from exc


def new_token() -> str:
    return secrets.token_urlsafe(32)
