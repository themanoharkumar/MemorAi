"""
Streak calculation service for MemorAI.
Returns consecutive calendar days (ending today or yesterday)
on which at least one flashcard review was completed.
"""

from datetime import datetime, timezone, timedelta


def calculate_streak(review_dates: list[datetime]) -> int:
    """
    Returns number of consecutive calendar days (ending today or yesterday)
    on which at least one flashcard review was completed.
    Returns 0 if no reviews exist or the last review was more than 1 day ago.
    """
    if not review_dates:
        return 0

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    # Normalize all dates to midnight UTC and deduplicate
    normalized = set()
    for d in review_dates:
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        midnight = d.replace(hour=0, minute=0, second=0, microsecond=0)
        normalized.add(midnight)

    # Sort descending
    days = sorted(normalized, reverse=True)

    # Streak must touch today or yesterday to be active
    if days[0] != today and days[0] != yesterday:
        return 0

    streak = 1
    for i in range(1, len(days)):
        if (days[i - 1] - days[i]).days == 1:
            streak += 1
        else:
            break

    return streak
