"""FastAPI dependencies: current user from the JWT, and role-based access control."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import decode_access_token
from database.session import get_db
from models import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    user = db.scalar(select(User).where(User.username == payload.get("sub")))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    """Dependency factory: allow only the given roles (403 otherwise)."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role}' cannot access this resource")
        return user

    return checker


ADMIN = ("admin",)
ADMIN_DOCTOR = ("admin", "doctor")
ADMIN_COORDINATOR = ("admin", "staff_coordinator")
ALL_ROLES = ("admin", "doctor", "staff_coordinator")
