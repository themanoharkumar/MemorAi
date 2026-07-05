"""
Decks API router for MemorAI.
Handles deck listing, deck deletion, and card CRUD operations (create, edit, delete).
All protected under user authentication.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, nulls_last
from sqlalchemy.orm import selectinload

from database.db import get_db
from models.models import Deck, Card, User
from schemas.schemas import DeckOut, DeckListItem, CardCreateRequest, CardEditRequest
from services.auth import get_current_user

router = APIRouter(prefix="/api/decks", tags=["decks"])


@router.get("")
async def get_decks(
    id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch all user decks (with card counts) or a single deck (with cards).
    Verifies ownership.
    """
    if id:
        # Single deck fetch
        result = await db.execute(
            select(Deck)
            .options(selectinload(Deck.cards))
            .where(Deck.id == id, Deck.user_id == current_user.id)
        )
        deck = result.scalar_one_or_none()
        if not deck:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or unauthorized.",
            )

        return {
            "deck": {
                "id": deck.id,
                "title": deck.title,
                "file_name": deck.file_name,
                "pdf_hash": deck.pdf_hash,
                "created_at": deck.created_at,
                "last_studied": deck.last_studied,
                "cards": sorted(
                    [
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
                        for c in deck.cards
                    ],
                    key=lambda c: c["due_date"],
                ),
            }
        }

    # Fetch all user decks with card counts
    result = await db.execute(
        select(Deck, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id)
        .group_by(Deck.id)
        .order_by(
            nulls_last(desc(Deck.last_studied)),
            desc(Deck.created_at),
        )
    )
    rows = result.all()

    return {
        "decks": [
            {
                "id": deck.id,
                "title": deck.title,
                "file_name": deck.file_name,
                "created_at": deck.created_at,
                "last_studied": deck.last_studied,
                "card_count": card_count,
            }
            for deck, card_count in rows
        ]
    }


@router.delete("")
async def delete_deck(
    id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a user deck (cascade deletes cards + review logs)."""
    result = await db.execute(
        select(Deck).where(Deck.id == id, Deck.user_id == current_user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found or unauthorized.",
        )

    await db.delete(deck)
    await db.commit()
    return {"success": True}


# ── Card CRUD Endpoints ───────────────────────────────────────────────────────

@router.post("/card")
async def create_card(
    body: CardCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually add a custom flashcard to an owned deck."""
    # Verify deck ownership
    deck_res = await db.execute(
        select(Deck).where(Deck.id == body.deck_id, Deck.user_id == current_user.id)
    )
    if not deck_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found or unauthorized.",
        )

    card = Card(
        id=str(uuid.uuid4()),
        front=body.front.strip(),
        back=body.back.strip(),
        topic=body.topic.strip() or "General",
        type=body.type,
        source=body.source,
        deck_id=body.deck_id,
    )
    db.add(card)
    await db.commit()
    return {"success": True, "card_id": card.id}


@router.put("/card")
async def edit_card(
    body: CardEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit an existing flashcard in an owned deck."""
    # Find card and verify deck ownership
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

    card.front = body.front.strip()
    card.back = body.back.strip()
    card.topic = body.topic.strip()
    card.type = body.type
    await db.commit()
    return {"success": True}


@router.delete("/card")
async def delete_card(
    card_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a flashcard from an owned deck."""
    card_res = await db.execute(
        select(Card)
        .join(Deck, Card.deck_id == Deck.id)
        .where(Card.id == card_id, Deck.user_id == current_user.id)
    )
    card = card_res.scalar_one_or_none()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found or unauthorized.",
        )

    await db.delete(card)
    await db.commit()
    return {"success": True}
