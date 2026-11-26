"""Password hashing and login tokens."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from app.constants.auth import TOKEN_HOURS

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(secret_key: str, user_id: UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": expires}, secret_key, algorithm=ALGORITHM)


def read_token(secret_key: str, token: str) -> UUID | None:
    """The user id a token was issued for, or None when it is invalid or expired."""
    try:
        return UUID(jwt.decode(token, secret_key, algorithms=[ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
