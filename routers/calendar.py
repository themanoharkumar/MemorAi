"""
Calendar API router for MemorAI.
Provides monthly heatmaps and day-level flashcard drill-downs.
"""

import re
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from database.db import get_db
from models.models import Card, Deck, ReviewLog, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _format_date_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _resolve_month_year(month_param: str | None, year_param: str | None) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    try:
        month = int(month_param) if month_param else now.month
        month = month if 1 <= month <= 12 else now.month
    except (ValueError, TypeError):
        month = now.month
    try:
        year = int(year_param) if year_param else now.year
        year = year if year >= 1970 else now.year
    except (ValueError, TypeError):
        year = now.year
    return month, year


def _get_mastery_state(repetitions: int, ease_factor: float) -> str:
    if repetitions >= 3 and ease_factor >= 2.0:
        return "mastered"
    if repetitions >= 1:
        return "learning"
    return "new"


@router.get("")
async def get_calendar(
    month: str | None = Query(default=None),
    year: str | None = Query(default=None),
    deck_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns month-level aggregate calendar data for the active user.
    All DB queries execute sequentially to prevent concurrent session conflicts.
    """
    resolved_month, resolved_year = _resolve_month_year(month, year)

    range_start = datetime(resolved_year, resolved_month, 1, tzinfo=timezone.utc)
    if resolved_month == 12:
        range_end = datetime(resolved_year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    else:
        range_end = datetime(resolved_year, resolved_month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_from_now = today_start + timedelta(days=7)

    # Base filters ensuring user scoping
    deck_filter_cards = [Card.due_date >= range_start, Card.due_date <= range_end, Deck.user_id == current_user.id]
    deck_filter_reviews = [ReviewLog.reviewed_at >= range_start, ReviewLog.reviewed_at <= range_end, Deck.user_id == current_user.id]
    deck_filter_due = [Deck.user_id == current_user.id]
    deck_filter_week = [Deck.user_id == current_user.id]
    deck_filter_month = [Deck.user_id == current_user.id]
    deck_filter_reviewed_today = [Deck.user_id == current_user.id]

    if deck_id:
        deck_filter_cards.append(Card.deck_id == deck_id)
        deck_filter_reviews.append(Card.deck_id == deck_id)
        deck_filter_due.append(Card.deck_id == deck_id)
        deck_filter_week.append(Card.deck_id == deck_id)
        deck_filter_month.append(Card.deck_id == deck_id)
        deck_filter_reviewed_today.append(Card.deck_id == deck_id)

    # Execute queries sequentially to prevent multi-statement transaction errors
    cards_result = await db.execute(
        select(Card.due_date, Card.deck_id, Deck.title)
        .join(Deck, Card.deck_id == Deck.id)
        .where(*deck_filter_cards)
    )
    cards = cards_result.all()

    review_logs_result = await db.execute(
        select(ReviewLog.reviewed_at, ReviewLog.rating)
        .join(Card, ReviewLog.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(*deck_filter_reviews)
    )
    review_logs = review_logs_result.all()

    due_count_result = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Card.due_date <= now, *deck_filter_due)
    )
    due_count = due_count_result.scalar() or 0

    reviewed_today_result = await db.execute(
        select(func.count(ReviewLog.id))
        .join(Card, ReviewLog.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(ReviewLog.reviewed_at >= today_start, *deck_filter_reviewed_today)
    )
    reviewed_today = reviewed_today_result.scalar() or 0

    due_this_week_result = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Card.due_date <= seven_days_from_now, *deck_filter_week)
    )
    due_this_week = due_this_week_result.scalar() or 0

    due_this_month_result = await db.execute(
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Card.due_date <= range_end, *deck_filter_month)
    )
    due_this_month = due_this_month_result.scalar() or 0

    # Build future days map
    future_map: dict[str, dict] = {}
    for card_row in cards:
        due = card_row.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        due_midnight = due.replace(hour=0, minute=0, second=0, microsecond=0)
        if due_midnight < today_start:
            continue
        date_key = _format_date_local(due_midnight)
        if date_key not in future_map:
            future_map[date_key] = {"date": date_key, "count": 0, "deck_breakdown": {}}
        future_map[date_key]["count"] += 1
        deck_entry = future_map[date_key]["deck_breakdown"]
        deck_title = card_row.title or "Untitled deck"
        card_deck_id = card_row.deck_id
        if card_deck_id not in deck_entry:
            deck_entry[card_deck_id] = {"deck_id": card_deck_id, "deck_title": deck_title, "count": 0}
        deck_entry[card_deck_id]["count"] += 1

    future_days = sorted(
        [
            {
                "date": v["date"],
                "count": v["count"],
                "deck_breakdown": list(v["deck_breakdown"].values()),
            }
            for v in future_map.values()
        ],
        key=lambda d: d["date"],
    )

    # Build past days map
    past_map: dict[str, dict] = {}
    for log_row in review_logs:
        reviewed = log_row.reviewed_at
        if reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=timezone.utc)
        reviewed_midnight = reviewed.replace(hour=0, minute=0, second=0, microsecond=0)
        if reviewed_midnight >= today_start:
            continue
        date_key = _format_date_local(reviewed_midnight)
        if date_key not in past_map:
            past_map[date_key] = {"date": date_key, "reviewed": 0, "correct": 0}
        past_map[date_key]["reviewed"] += 1
        if log_row.rating >= 2:
            past_map[date_key]["correct"] += 1

    past_days = sorted(past_map.values(), key=lambda d: d["date"])

    today_stats = {
        "date": _format_date_local(today_start),
        "due_count": due_count,
        "reviewed_today": reviewed_today,
        "due_this_week": due_this_week,
        "due_this_month": due_this_month,
    }

    return {"future_days": future_days, "past_days": past_days, "today_stats": today_stats}


@router.get("/cards")
async def get_calendar_cards(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    type: str = Query(..., description="'due' or 'reviewed'"),
    deck_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns card-level detail for a specific calendar day.
    Includes validation to verify ownership.
    """
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        raise HTTPException(status_code=400, detail="date (YYYY-MM-DD) is required")
    if type not in ("due", "reviewed"):
        raise HTTPException(status_code=400, detail="type must be 'due' or 'reviewed'")

    # Validate deck ownership if filter provided
    if deck_id:
        deck_res = await db.execute(
            select(Deck).where(Deck.id == deck_id, Deck.user_id == current_user.id)
        )
        if not deck_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Deck not found or unauthorized")

    year, month, day = map(int, date.split("-"))
    day_start = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(year, month, day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    is_today = _format_date_local(day_start) == _format_date_local(today_start)

    if type == "due":
        if is_today:
            due_where = or_(
                and_(Card.due_date >= day_start, Card.due_date <= day_end),
                Card.due_date < today_start,
            )
        else:
            due_where = and_(Card.due_date >= day_start, Card.due_date <= day_end)

        base_where = [due_where, Deck.user_id == current_user.id]
        if deck_id:
            base_where.append(Card.deck_id == deck_id)

        cards_result = await db.execute(
            select(Card, Deck.title.label("deck_title"))
            .join(Deck, Card.deck_id == Deck.id)
            .where(*base_where)
            .order_by(Deck.title.asc(), Card.topic.asc())
        )
        card_rows = cards_result.all()

        reviewed_today = 0
        if is_today:
            rt_where = [ReviewLog.reviewed_at >= today_start, ReviewLog.reviewed_at <= day_end, Deck.user_id == current_user.id]
            if deck_id:
                rt_where.append(Card.deck_id == deck_id)
            rt_result = await db.execute(
                select(func.count(ReviewLog.id))
                .join(Card, ReviewLog.card_id == Card.id)
                .join(Deck, Card.deck_id == Deck.id)
                .where(*rt_where)
            )
            reviewed_today = rt_result.scalar() or 0

        cards_out = []
        deck_map: dict[str, dict] = {}
        for card, deck_title in card_rows:
            mastery_state = _get_mastery_state(card.repetitions, card.ease_factor)
            cards_out.append({
                "id": card.id,
                "front": card.front,
                "back": card.back,
                "topic": card.topic,
                "type": card.type,
                "source": card.source,
                "ease_factor": card.ease_factor,
                "interval": card.interval,
                "repetitions": card.repetitions,
                "due_date": card.due_date,
                "deck": {"id": card.deck_id, "title": deck_title},
                "mastery_state": mastery_state,
            })
            if card.deck_id not in deck_map:
                deck_map[card.deck_id] = {"deck_id": card.deck_id, "deck_title": deck_title, "count": 0}
            deck_map[card.deck_id]["count"] += 1

        deck_summary = sorted(deck_map.values(), key=lambda d: d["deck_title"])
        today_stats_out = {"due_count": len(cards_out), "reviewed_today": reviewed_today} if is_today else None

        return {
            "cards": cards_out,
            "date": date,
            "total_count": len(cards_out),
            "type": type,
            "deck_summary": deck_summary,
            **({"today_stats": today_stats_out} if today_stats_out else {}),
        }

    # type == "reviewed"
    rev_where = [ReviewLog.reviewed_at >= day_start, ReviewLog.reviewed_at <= day_end, Deck.user_id == current_user.id]
    if deck_id:
        rev_where.append(Card.deck_id == deck_id)

    logs_result = await db.execute(
        select(ReviewLog.reviewed_at, ReviewLog.rating, Card.id, Card.front, Card.topic, Card.deck_id, Deck.title.label("deck_title"))
        .join(Card, ReviewLog.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(*rev_where)
        .order_by(ReviewLog.reviewed_at.asc())
    )
    log_rows = logs_result.all()

    cards_out = []
    deck_map: dict[str, dict] = {}
    for row in log_rows:
        cards_out.append({
            "id": row.id,
            "front": row.front,
            "topic": row.topic,
            "deck": {"id": row.deck_id, "title": row.deck_title},
            "rating": row.rating,
        })
        if row.deck_id not in deck_map:
            deck_map[row.deck_id] = {"deck_id": row.deck_id, "deck_title": row.deck_title, "count": 0}
        deck_map[row.deck_id]["count"] += 1

    deck_summary = sorted(deck_map.values(), key=lambda d: d["deck_title"])
    return {
        "cards": cards_out,
        "date": date,
        "total_count": len(cards_out),
        "type": type,
        "deck_summary": deck_summary,
    }
