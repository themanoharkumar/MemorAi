"""
Schedule API router for MemorAI.
Provides a 14-day review schedule forecast for a specific deck.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.db import get_db
from models.models import Card, Deck, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("")
async def get_schedule(
    deck_id: str = Query(..., description="Deck ID to get schedule for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a 14-day review schedule for a deck (verified by owner)."""
    # Verify ownership
    deck_res = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == current_user.id)
    )
    if not deck_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found or unauthorized.",
        )

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fourteen_days_later = now + timedelta(days=14)

    # Cards already due today (overdue + today)
    today_due_result = await db.execute(
        select(func.count(Card.id)).where(
            Card.deck_id == deck_id,
            Card.due_date <= now,
        )
    )
    today_due_count = today_due_result.scalar() or 0

    # Future cards due in the next 14 days
    future_result = await db.execute(
        select(Card.due_date).where(
            Card.deck_id == deck_id,
            Card.due_date > now,
            Card.due_date <= fourteen_days_later,
        ).order_by(Card.due_date.asc())
    )
    future_due_dates = future_result.scalars().all()

    # Group by calendar date
    groups: dict[str, int] = {}
    for due_date in future_due_dates:
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        date_key = due_date.strftime("%Y-%m-%d")
        groups[date_key] = groups.get(date_key, 0) + 1

    today_key = today_start.strftime("%Y-%m-%d")
    tomorrow = today_start + timedelta(days=1)
    tomorrow_key = tomorrow.strftime("%Y-%m-%d")

    schedule = []

    # Add today if there are due cards
    if today_due_count > 0:
        schedule.append({
            "date": today_key,
            "count": today_due_count,
            "is_today": True,
            "label": "Today",
        })

    # Add future dates
    for date_key in sorted(groups.keys()):
        if date_key == tomorrow_key:
            label = "Tomorrow"
        else:
            dt = datetime.strptime(date_key, "%Y-%m-%d")
            # Cross-platform day formatting without leading zero
            label = f"{dt.strftime('%a, %b')} {dt.day}"

        schedule.append({
            "date": date_key,
            "count": groups[date_key],
            "is_today": False,
            "label": label,
        })

    # Next review time (nearest future dueDate)
    next_card_result = await db.execute(
        select(Card.due_date).where(
            Card.deck_id == deck_id,
            Card.due_date > now,
        ).order_by(Card.due_date.asc()).limit(1)
    )
    next_due = next_card_result.scalar_one_or_none()

    return {
        "schedule": schedule,
        "next_review_at": next_due,
        "today_due_count": today_due_count,
    }
