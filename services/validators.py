"""
Flashcard and PDF validators for MemorAI.
Validates PDF uploads before processing and generated flashcards
before saving to the database.
"""

import re
from dataclasses import dataclass
from typing import Any, Literal

VALID_TYPES = {"definition", "application", "relationship", "edge_case"}
VALID_SOURCES = {"text", "visual", "both"}
URL_RE = re.compile(r'https?://', re.IGNORECASE)
INJECTION_RE = re.compile(
    r'ignore previous|pretend|act as|you are now|system prompt',
    re.IGNORECASE
)


@dataclass
class ValidatedCard:
    front: str
    back: str
    topic: str
    type: Literal["definition", "application", "relationship", "edge_case"]
    source: Literal["text", "visual", "both"]


def validate_pdf_upload(
    data: bytes,
    file_name: str,
    file_size_bytes: int
) -> dict[str, Any]:
    """
    Server-side PDF validation. Runs before any processing.
    Returns {'valid': True} or {'valid': False, 'error': '...'}
    """
    if file_size_bytes > 20 * 1024 * 1024:
        return {"valid": False, "error": "File too large. Maximum size is 20MB."}

    if not file_name.lower().endswith(".pdf"):
        return {"valid": False, "error": "Only PDF files are accepted."}

    # Magic bytes check — every valid PDF starts with %PDF
    if not data[:4] == b'%PDF':
        return {"valid": False, "error": "Invalid file. Please upload a valid PDF."}

    return {"valid": True}


def validate_flashcards(raw_cards: list[Any]) -> list[ValidatedCard]:
    """
    Flashcard output validation. Runs after Gemini responds.
    Guards against malformed JSON, prompt injection, and out-of-range content.
    """
    if not isinstance(raw_cards, list):
        return []

    validated: list[ValidatedCard] = []

    for c in raw_cards:
        if not isinstance(c, dict):
            continue

        front = c.get("front")
        back = c.get("back")

        if not isinstance(front, str) or not isinstance(back, str):
            continue
        if len(front) < 10 or len(front) > 300:
            continue
        if len(back) < 10 or len(back) > 600:
            continue
        if URL_RE.search(front) or URL_RE.search(back):
            continue
        if INJECTION_RE.search(front) or INJECTION_RE.search(back):
            continue

        topic_raw = c.get("topic", "")
        topic = topic_raw.strip() if isinstance(topic_raw, str) and topic_raw.strip() else "General"

        card_type = c.get("type", "definition")
        if card_type not in VALID_TYPES:
            card_type = "definition"

        card_source = c.get("source", "text")
        if card_source not in VALID_SOURCES:
            card_source = "text"

        validated.append(ValidatedCard(
            front=front.strip(),
            back=back.strip(),
            topic=topic,
            type=card_type,
            source=card_source,
        ))

    return validated
