"""
Authentication and security helpers for MemorAI.
Handles password hashing via bcrypt, JWT tokens, and FastAPI dependencies.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import bcrypt
import jwt
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.db import get_db
from models.models import User

SECRET_KEY = os.environ.get("JWT_SECRET", "memorai-super-secret-key-change-in-production")
ALGORITHM = "HS256"
COOKIE_NAME = "access_token"
ACCESS_TOKEN_EXPIRE_DAYS = 7


class UnauthenticatedException(Exception):
    """Custom exception raised when a browser user is not logged in."""
    pass


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hashed value."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    """Create a signed JWT token valid for 7 days."""
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Decode a JWT token and return the user_id if valid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that returns the current authenticated User.
    Raises 401 Unauthorized — used for API endpoints.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Dependency that returns the current user, or None if not authenticated."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    user_id = decode_access_token(token)
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that returns the current authenticated User for browser pages.
    Raises UnauthenticatedException if not logged in (to trigger /login redirect).
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise UnauthenticatedException()

    user_id = decode_access_token(token)
    if not user_id:
        raise UnauthenticatedException()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthenticatedException()

    return user
