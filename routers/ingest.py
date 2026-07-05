"""
Ingest API router for MemorAI.
Processes PDF uploads and generates study decks. Secured under user auth.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile, status, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.db import get_db, AsyncSessionLocal
from models.models import Deck, Card, User
from services.auth import get_current_user
from services.validators import validate_pdf_upload, validate_flashcards
from services.pdf_parser import (
    detect_pdf_type,
    extract_text_from_pdf,
    get_pdf_page_count,
    extract_text_by_chunks,
    hash_pdf,
    CHUNK_THRESHOLD,
    CHUNK_SIZE,
)
from services.gemini import (
    generate_with_vision,
    generate_with_text,
    generate_from_chunks,
    GeminiRateLimitError,
)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _encode(data: dict) -> bytes:
    return (json.dumps(data, default=str) + "\n").encode("utf-8")


@router.post("")
async def ingest_pdf(
    pdf: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts a PDF file, processes it with Gemini, and saves flashcards.
    Streams NDJSON progress events back to the client. Scoped to current user.
    """
    pdf_data = await pdf.read()
    file_name = pdf.filename or "upload.pdf"
    file_size = len(pdf_data)

    # Security validation before streaming starts
    validation = validate_pdf_upload(pdf_data, file_name, file_size)
    if not validation["valid"]:
        async def error_stream():
            yield _encode({"status": "error", "error": validation["error"]})
        return StreamingResponse(error_stream(), media_type="application/x-ndjson")

    async def generate():
        # Use a fresh session inside the generator
        async with AsyncSessionLocal() as db:
            try:
                # Duplicate detection for this specific user
                pdf_hash = hash_pdf(pdf_data)
                existing = await db.execute(
                    select(Deck).where(
                        Deck.pdf_hash == pdf_hash,
                        Deck.user_id == current_user.id,
                    )
                )
                existing_deck = existing.scalar_one_or_none()
                if existing_deck:
                    yield _encode({"status": "done", "existing": True, "deck_id": existing_deck.id})
                    return

                yield _encode({"status": "analyzing"})

                page_count = get_pdf_page_count(pdf_data)
                pdf_type = "text"

                if page_count > CHUNK_THRESHOLD:
                    pdf_type = detect_pdf_type(pdf_data, max_pages=10, skip_pages=10)
                    if pdf_type == "vision":
                        yield _encode({
                            "status": "error",
                            "error": "This PDF is too large and contains too many images to be processed automatically. Please try a smaller file or a text-heavy PDF.",
                        })
                        return
                else:
                    pdf_type = detect_pdf_type(pdf_data)

                # Calculate ETA
                BASE_OVERHEAD = 10
                CHUNK_CALL_SECONDS = 22
                TEXT_BASE = 8
                TEXT_PER_PAGE = 1.2
                VISION_BASE = 10
                VISION_PER_PAGE = 1.0

                estimated_seconds = BASE_OVERHEAD
                if page_count > CHUNK_THRESHOLD:
                    chunks_count = (page_count + CHUNK_SIZE - 1) // CHUNK_SIZE
                    estimated_seconds += chunks_count * CHUNK_CALL_SECONDS
                    estimated_seconds = max(15, round(estimated_seconds * 1.15))
                elif pdf_type == "vision":
                    estimated_seconds += VISION_BASE + page_count * VISION_PER_PAGE
                    estimated_seconds = max(12, round(estimated_seconds * 1.05))
                else:
                    estimated_seconds += TEXT_BASE + page_count * TEXT_PER_PAGE
                    estimated_seconds = max(10, round(estimated_seconds * 1.1))

                yield _encode({
                    "status": "processing",
                    "page_count": page_count,
                    "pdf_type": pdf_type,
                    "estimated_seconds": estimated_seconds,
                })

                if page_count > CHUNK_THRESHOLD:
                    chunks = extract_text_by_chunks(pdf_data, CHUNK_SIZE)
                    total_text_length = sum(len(c["text"].strip()) for c in chunks)
                    if total_text_length < 50:
                        yield _encode({"status": "error", "error": "This PDF appears to be empty or contains no readable text."})
                        return
                    raw_cards = await generate_from_chunks(chunks)
                else:
                    if pdf_type == "vision":
                        raw_cards = await generate_with_vision(pdf_data)
                    else:
                        text = extract_text_from_pdf(pdf_data)
                        if len(text.strip()) < 50:
                            yield _encode({"status": "error", "error": "This PDF appears to be empty or contains no readable text."})
                            return
                        raw_cards = await generate_with_text(text)

                valid_cards = validate_flashcards([vars(c) for c in raw_cards])
                if not valid_cards:
                    yield _encode({"status": "error", "error": "No valid flashcards could be generated from this PDF. Try a different file."})
                    return

                yield _encode({"status": "saving"})

                # Save deck linked to current user
                deck_title = title or file_name.replace(".pdf", "").replace(".PDF", "")
                deck_id = str(uuid.uuid4())
                deck = Deck(
                    id=deck_id,
                    title=deck_title,
                    file_name=file_name,
                    pdf_hash=pdf_hash,
                    user_id=current_user.id,
                )
                db.add(deck)

                for vc in valid_cards:
                    card = Card(
                        id=str(uuid.uuid4()),
                        front=vc.front,
                        back=vc.back,
                        topic=vc.topic,
                        type=vc.type,
                        source=vc.source,
                        deck_id=deck_id,
                    )
                    db.add(card)

                await db.commit()
                await db.refresh(deck)

                yield _encode({
                    "status": "done",
                    "existing": False,
                    "deck": {
                        "id": deck.id,
                        "title": deck.title,
                        "file_name": deck.file_name,
                        "created_at": deck.created_at,
                        "card_count": len(valid_cards),
                    },
                })

            except GeminiRateLimitError as err:
                print(f"[ingest] rate limit error: {err}")
                yield _encode({
                    "status": "error",
                    "error": str(err),
                    "retry_after_seconds": err.retry_after_seconds,
                })
            except Exception as err:
                print(f"[ingest] error: {err}")
                yield _encode({
                    "status": "error",
                    "error": "Something went wrong processing your PDF. Please try again.",
                })

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )
