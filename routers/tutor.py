"""
AI Tutor API router for MemorAI.
Provides context-aware tutoring and clarifications for user study decks.
"""

import os
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from google import genai
from database.db import get_db
from models.models import Deck, Card, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

MODEL = "gemini-2.5-flash"


class ChatMessage(BaseModel):
    role: Literal["user", "model"]
    content: str


class TutorChatRequest(BaseModel):
    deck_id: str
    message: str = Field(..., min_length=1, max_length=1000)
    history: list[ChatMessage] = []


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    return genai.Client(api_key=api_key)


@router.post("/chat")
async def chat_with_tutor(
    body: TutorChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate tutor response based on deck's cards and chat history.
    """
    # 1. Fetch deck and verify ownership
    deck_res = await db.execute(
        select(Deck)
        .options(selectinload(Deck.cards))
        .where(Deck.id == body.deck_id, Deck.user_id == current_user.id)
    )
    deck = deck_res.scalar_one_or_none()
    if not deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found or unauthorized.",
        )

    # 2. Build cards context
    cards_text = ""
    for idx, c in enumerate(deck.cards, 1):
        cards_text += f"Card {idx} (Topic: {c.topic}): Question: {c.front} | Answer: {c.back}\n"

    # 3. Format history for system context
    hist_text = ""
    for msg in body.history:
        sender = "Student" if msg.role == "user" else "Tutor"
        hist_text += f"{sender}: {msg.content}\n"

    system_prompt = f"""You are a helpful, encouraging, and intelligent academic tutor helping a student study a deck of flashcards.
The deck is titled "{deck.title}" and contains the following study cards:

{cards_text}

---
Student study guidelines:
- Answer questions accurately, concisely, and helpfully.
- Keep your answers under 5 sentences unless a longer explanation is explicitly requested.
- Use bullet points, bold text, or lists to make formatting clean.
- Do not mention system context variables, like 'I have a list of cards' or 'the cards provided'. Speak naturally as if you know the topic perfectly.
- You can provide analogies, definitions, or clarify details of the answers.

Here is the conversation history:
{hist_text}
Student: {body.message}
Tutor:"""

    try:
        client = _get_client()
        response = await genai.Client.aio().models.generate_content(
            model=MODEL,
            contents=[system_prompt]
        )
        return {"response": response.text}
    except Exception as err:
        print(f"[tutor] AI generation failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Tutor is temporarily unavailable. Please try again shortly.",
        )
