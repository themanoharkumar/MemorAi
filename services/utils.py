"""
Utility helpers for MemorAI.
"""

from datetime import datetime, timezone


def relative_date(dt: datetime | None) -> str:
    """Returns a human-readable relative date string."""
    if dt is None:
        return "Never studied"

    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    then = dt.replace(hour=0, minute=0, second=0, microsecond=0)

    diff_days = (then - now).days

    if diff_days == 0:
        return "Today"

    if diff_days > 0:
        # Future dates
        if diff_days == 1:
            return "Tomorrow"
        if diff_days < 7:
            return f"in {diff_days} days"
        if diff_days < 30:
            return f"in {round(diff_days / 7)} weeks"
        if diff_days < 365:
            return f"in {round(diff_days / 30)} months"
        return f"in {round(diff_days / 365)} years"
    else:
        # Past dates
        past_days = abs(diff_days)
        if past_days == 1:
            return "Yesterday"
        if past_days < 7:
            return f"{past_days} days ago"
        if past_days < 30:
            return f"{round(past_days / 7)} weeks ago"
        if past_days < 365:
            return f"{round(past_days / 30)} months ago"
        return f"{round(past_days / 365)} years ago"
