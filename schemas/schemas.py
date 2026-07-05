"""
Pydantic request/response schemas for MemorAI API.
Replaces the implicit TypeScript interfaces used in the Next.js routes.
"""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Cards ─────────────────────────────────────────────────────────────────────

class CardOut(BaseModel):
    id: str
    front: str
    back: str
    topic: str
    type: str
    source: str
    deck_id: str
    ease_factor: float
    interval: int
    repetitions: int
    due_date: datetime

    model_config = {"from_attributes": True}


class CardWithDeck(CardOut):
    deck: "DeckBrief"

    model_config = {"from_attributes": True}


# ── Decks ─────────────────────────────────────────────────────────────────────

class DeckBrief(BaseModel):
    id: str
    title: str

    model_config = {"from_attributes": True}


class DeckOut(BaseModel):
    id: str
    title: str
    file_name: str
    pdf_hash: str
    created_at: datetime
    last_studied: datetime | None
    cards: list[CardOut] = []

    model_config = {"from_attributes": True}


class DeckListItem(BaseModel):
    id: str
    title: str
    file_name: str
    created_at: datetime
    last_studied: datetime | None
    card_count: int

    model_config = {"from_attributes": True}


# ── Review ────────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    card_id: str
    rating: int = Field(..., ge=0, le=3, description="0=Again 1=Hard 2=Good 3=Easy")


class ReviewResponse(BaseModel):
    card: CardOut
    next_due: datetime


# ── Study ────────────────────────────────────────────────────────────────────

class StudyResponse(BaseModel):
    cards: list[CardOut]
    total_due: int
    has_more: bool


# ── Stats ────────────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    deck_id: str
    mastered: int
    shaky: int
    new_cards: int
    due_today: int
    total: int
    reviewed_today: int
    mastery_percent: int
    retention_rate: float
    streak: int
    last_studied: datetime | None
    created_at: datetime | None


# ── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleDay(BaseModel):
    date: str
    count: int
    is_today: bool
    label: str


class ScheduleResponse(BaseModel):
    schedule: list[ScheduleDay]
    next_review_at: datetime | None
    today_due_count: int


# ── Calendar ─────────────────────────────────────────────────────────────────

class DeckBreakdown(BaseModel):
    deck_id: str
    deck_title: str
    count: int


class FutureDay(BaseModel):
    date: str
    count: int
    deck_breakdown: list[DeckBreakdown]


class PastDay(BaseModel):
    date: str
    reviewed: int
    correct: int


class TodayStats(BaseModel):
    date: str
    due_count: int
    reviewed_today: int
    due_this_week: int
    due_this_month: int


class CalendarResponse(BaseModel):
    future_days: list[FutureDay]
    past_days: list[PastDay]
    today_stats: TodayStats


# ── Calendar Cards ────────────────────────────────────────────────────────────

class DeckSummary(BaseModel):
    deck_id: str
    deck_title: str
    count: int


class MasteryState(BaseModel):
    state: Literal["mastered", "learning", "new"]


class DueCardOut(BaseModel):
    id: str
    front: str
    back: str
    topic: str
    type: str
    source: str
    ease_factor: float
    interval: int
    repetitions: int
    due_date: datetime
    deck: DeckBrief
    mastery_state: Literal["mastered", "learning", "new"]


class ReviewedCardOut(BaseModel):
    id: str
    front: str
    topic: str
    deck: DeckBrief
    rating: int


class CalendarCardsResponse(BaseModel):
    cards: list[Any]
    date: str
    total_count: int
    type: Literal["due", "reviewed"]
    deck_summary: list[DeckSummary]
    today_stats: dict | None = None


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestProgressEvent(BaseModel):
    status: Literal["analyzing", "processing", "saving", "done", "error"]
    existing: bool | None = None
    deck_id: str | None = None
    deck: DeckOut | None = None
    page_count: int | None = None
    pdf_type: str | None = None
    estimated_seconds: int | None = None
    error: str | None = None
    retry_after_seconds: int | None = None


# ── Authentication ────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_\-]+$")
    email: str = Field(..., max_length=50)
    password: str = Field(..., min_length=6, max_length=32)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Custom Card CRUD ─────────────────────────────────────────────────────────

class CardCreateRequest(BaseModel):
    deck_id: str
    front: str = Field(..., min_length=10, max_length=300)
    back: str = Field(..., min_length=10, max_length=600)
    topic: str = Field("General", max_length=50)
    type: Literal["definition", "application", "relationship", "edge_case"] = "definition"
    source: Literal["text", "visual", "both"] = "text"


class CardEditRequest(BaseModel):
    card_id: str
    front: str = Field(..., min_length=10, max_length=300)
    back: str = Field(..., min_length=10, max_length=600)
    topic: str = Field(..., min_length=1, max_length=50)
    type: Literal["definition", "application", "relationship", "edge_case"]
