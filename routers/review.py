"""
Review API router for MemorAI.
Accepts flashcard reviews and updates SM-2 parameters. Secured under user auth.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.db import get_db
from models.models import Card, ReviewLog, Deck, User
from schemas.schemas import ReviewRequest
from services.auth import get_current_user
from services.sm2 import SM2Input, calculate_sm2

router = APIRouter(prefix="/api/review", tags=["review"])


@router.post("")
async def submit_review(
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submits a card review, runs the SM-2 algorithm, and logs the review.
    Verifies that the card belongs to a deck owned by the user.
    """
    # Join with Deck to verify ownership
    card_res = await db.execute(
        select(Card)
        .join(Deck, Card.deck_id == Deck.id)
        .where(Card.id == body.card_id, Deck.user_id == current_user.id)
    )
    card = card_res.scalar_one_or_none()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found or unauthorized.",
        )

    sm2_result = calculate_sm2(SM2Input(
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
        rating=body.rating,
    ))

    # Atomic database update
    card.ease_factor = sm2_result.ease_factor
    card.interval = sm2_result.interval
    card.repetitions = sm2_result.repetitions
    card.due_date = sm2_result.due_date

    review_log = ReviewLog(
        card_id=body.card_id,
        rating=body.rating,
    )
    db.add(review_log)

    deck_res = await db.execute(select(Deck).where(Deck.id == card.deck_id))
    deck = deck_res.scalar_one_or_none()
    if deck:
        deck.last_studied = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(card)

    return {
        "card": {
            "id": card.id,
            "front": card.front,
            "back": card.back,
            "topic": card.topic,
            "type": card.type,
            "source": card.source,
            "deck_id": card.deck_id,
            "ease_factor": card.ease_factor,
            "interval": card.interval,
            "repetitions": card.repetitions,
            "due_date": card.due_date,
        },
        "next_due": sm2_result.due_date,
    }
