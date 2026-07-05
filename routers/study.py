"""
Study API router for MemorAI.
Fetches cards due for review in a deck. Secured under user auth.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.db import get_db
from models.models import Card, Deck, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/study", tags=["study"])


@router.get("")
async def get_due_cards(
    deck_id: str = Query(..., description="Deck ID to fetch due cards for"),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns cards due for review in an owned deck.
    Verifies deck ownership first.
    """
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

    # Count due and fetch cards sequentially
    count_result = await db.execute(
        select(func.count(Card.id))
        .where(Card.deck_id == deck_id, Card.due_date <= now)
    )
    total_due = count_result.scalar() or 0

    cards_result = await db.execute(
        select(Card)
        .where(Card.deck_id == deck_id, Card.due_date <= now)
        .order_by(Card.due_date.asc())
        .limit(limit)
    )
    cards = cards_result.scalars().all()

    return {
        "cards": [
            {
                "id": c.id,
                "front": c.front,
                "back": c.back,
                "topic": c.topic,
                "type": c.type,
                "source": c.source,
                "deck_id": c.deck_id,
                "ease_factor": c.ease_factor,
                "interval": c.interval,
                "repetitions": c.repetitions,
                "due_date": c.due_date,
            }
            for c in cards
        ],
        "total_due": total_due,
        "has_more": total_due > limit,
    }
