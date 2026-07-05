"""
Authentication API endpoints for MemorAI.
Handles signup, login (cookie injection), logout (cookie removal), and active profile checking.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.db import get_db
from models.models import User
from schemas.schemas import UserRegisterRequest, UserLoginRequest, UserOut
from services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    COOKIE_NAME,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
async def register_user(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    # Check username
    existing_username = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )

    # Check email
    existing_email = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered.",
        )

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login")
async def login_user(
    body: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and set secure, HTTP-only cookie.
    Allows login via username or email.
    """
    query = select(User).where(
        (User.username == body.username) | (User.email == body.username)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(user.id)

    # Inject JWT cookie (HTTP-only, secure, samesite Lax)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days in seconds
        expires=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False,  # In development, HTTP is okay. Secure=True in prod
    )

    return {"success": True, "username": user.username}


@router.post("/logout")
async def logout_user(response: Response):
    """Log out user by deleting the session cookie."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )
    return {"success": True}


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Get active authenticated user profile details."""
    return current_user
