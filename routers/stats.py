"""
Stats API router for MemorAI.
Provides mastery, retention, and streak metrics for a specific deck or globally.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, not_

from database.db import get_db
from models.models import Card, Deck, ReviewLog, User
from services.auth import get_current_user
from services.streak import calculate_streak

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/global")
async def get_global_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns global progress statistics across all user decks.
    Queries run sequentially on the single session to prevent concurrency errors.
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Total decks owned by user
    total_decks_res = await db.execute(
        select(func.count(Deck.id)).where(Deck.user_id == current_user.id)
    )
    total_decks = total_decks_res.scalar() or 0

    # If user has no decks, return early empty stats
    if total_decks == 0:
        return {
            "total_decks": 0,
            "total_cards": 0,
            "mastered": 0,
            "shaky": 0,
            "new_cards": 0,
            "due_today": 0,
            "reviewed_today": 0,
            "mastery_percent": 0,
            "retention_rate": 0.0,
            "streak": 0,
        }

    # 2. Total cards
    total_cards_res = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id)
    )
    total_cards = total_cards_res.scalar() or 0

    # 3. Mastered cards (reps >= 2 and EF >= 2.0)
    mastered_res = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(
            Deck.user_id == current_user.id,
            Card.repetitions >= 2,
            Card.ease_factor >= 2.0,
        )
    )
    mastered = mastered_res.scalar() or 0

    # 4. Shaky cards
    shaky_res = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(
            Deck.user_id == current_user.id,
            Card.repetitions >= 1,
            not_(and_(Card.repetitions >= 2, Card.ease_factor >= 2.0)),
        )
    )
    shaky = shaky_res.scalar() or 0

    # 5. New cards
    new_res = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id, Card.repetitions == 0)
    )
    new_cards = new_res.scalar() or 0

    # 6. Due today
    due_res = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id, Card.due_date <= now)
    )
    due_today = due_res.scalar() or 0

    # 7. Recent review logs (for retention and streak)
    reviews_res = await db.execute(
        select(ReviewLog.rating, ReviewLog.reviewed_at)
        .join(Card, ReviewLog.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(
            Deck.user_id == current_user.id,
            ReviewLog.reviewed_at >= thirty_days_ago,
        )
    )
    recent_reviews = reviews_res.all()

    reviewed_today = sum(1 for r in recent_reviews if r.reviewed_at >= start_of_today)

    retention_rate = 0.0
    if recent_reviews:
        correct = sum(1 for r in recent_reviews if r.rating >= 2)
        retention_rate = round(correct / len(recent_reviews), 2)

    streak = calculate_streak([r.reviewed_at for r in recent_reviews])
    mastery_percent = round((mastered / total_cards) * 100) if total_cards > 0 else 0

    return {
        "total_decks": total_decks,
        "total_cards": total_cards,
        "mastered": mastered,
        "shaky": shaky,
        "new_cards": new_cards,
        "due_today": due_today,
        "reviewed_today": reviewed_today,
        "mastery_percent": mastery_percent,
        "retention_rate": retention_rate,
        "streak": streak,
    }


@router.get("")
async def get_stats(
    deck_id: str = Query(..., description="Deck ID to fetch stats for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns mastery, retention, and streak stats for a single deck.
    Queries execute sequentially to avoid transaction overlaps.
    """
    # Verify ownership
    deck_res = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == current_user.id)
    )
    deck = deck_res.scalar_one_or_none()
    if not deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found or unauthorized.",
        )

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Mastered
    mastered_res = await db.execute(
        select(func.count(Card.id)).where(
            Card.deck_id == deck_id,
            Card.repetitions >= 2,
            Card.ease_factor >= 2.0,
        )
    )
    mastered = mastered_res.scalar() or 0

    # 2. Shaky
    shaky_res = await db.execute(
        select(func.count(Card.id)).where(
            Card.deck_id == deck_id,
            Card.repetitions >= 1,
            not_(and_(Card.repetitions >= 2, Card.ease_factor >= 2.0)),
        )
    )
    shaky = shaky_res.scalar() or 0

    # 3. New
    new_res = await db.execute(
        select(func.count(Card.id)).where(
            Card.deck_id == deck_id,
            Card.repetitions == 0,
        )
    )
    new_cards = new_res.scalar() or 0

    # 4. Due today
    due_res = await db.execute(
        select(func.count(Card.id)).where(
            Card.deck_id == deck_id,
            Card.due_date <= now,
        )
    )
    due_today = due_res.scalar() or 0

    # 5. Total
    total_res = await db.execute(
        select(func.count(Card.id)).where(Card.deck_id == deck_id)
    )
    total = total_res.scalar() or 0

    # 6. Recent reviews
    reviews_res = await db.execute(
        select(ReviewLog.rating, ReviewLog.reviewed_at)
        .join(Card, ReviewLog.card_id == Card.id)
        .where(
            Card.deck_id == deck_id,
            ReviewLog.reviewed_at >= thirty_days_ago,
        )
    )
    recent_reviews = reviews_res.all()

    reviewed_today = sum(1 for r in recent_reviews if r.reviewed_at >= start_of_today)

    retention_rate = 0.0
    if recent_reviews:
        correct = sum(1 for r in recent_reviews if r.rating >= 2)
        retention_rate = round(correct / len(recent_reviews), 2)

    streak = calculate_streak([r.reviewed_at for r in recent_reviews])
    mastery_percent = round((mastered / total) * 100) if total > 0 else 0

    return {
        "deck_id": deck_id,
        "mastered": mastered,
        "shaky": shaky,
        "new_cards": new_cards,
        "due_today": due_today,
        "total": total,
        "reviewed_today": reviewed_today,
        "mastery_percent": mastery_percent,
        "retention_rate": retention_rate,
        "streak": streak,
        "last_studied": deck.last_studied,
        "created_at": deck.created_at,
    }
