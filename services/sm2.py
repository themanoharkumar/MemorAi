"""
SM-2 spaced repetition algorithm for MemorAI.
Direct Python port of lib/sm2.ts

Rating scale:
  0 = Again  → complete failure, reset streak, re-queue in session
  1 = Hard   → passed but struggled, shorter next interval (PASS, not failure)
  2 = Good   → solid recall, standard SM-2 progression
  3 = Easy   → effortless recall, boosted interval
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SM2Input:
    ease_factor: float   # starts at 2.5, floor is 1.3
    interval: int        # days until next review
    repetitions: int     # count of consecutive successful reviews
    rating: int          # 0=Again 1=Hard 2=Good 3=Easy


@dataclass
class SM2Output:
    ease_factor: float
    interval: int
    repetitions: int
    due_date: datetime


def calculate_sm2(input: SM2Input) -> SM2Output:
    ease_factor = input.ease_factor
    interval = input.interval
    repetitions = input.repetitions
    rating = input.rating

    # Update ease factor for every rating (formula adapted for 0-3 scale)
    # rating=3 (Easy):  EF += +0.10  (grows faster)
    # rating=2 (Good):  EF +=  0.00  (neutral)
    # rating=1 (Hard):  EF += -0.14  (grows slower)
    # rating=0 (Again): EF += -0.32  (grows much slower)
    ease_factor = ease_factor + 0.1 - (3 - rating) * (0.08 + (3 - rating) * 0.02)
    ease_factor = max(1.3, round(ease_factor, 2))

    if rating == 0:
        # Again — complete failure: reset streak, show again tomorrow
        repetitions = 0
        interval = 1

    elif rating == 1:
        # Hard — passed but struggled. Keep the streak, shorter interval.
        # Hard is a PASS, not a failure. Card is NOT re-shown this session.
        if repetitions == 0:
            interval = 1        # first time → come back tomorrow
        elif repetitions == 1:
            interval = 3        # instead of 6 days (Good), come back in 3
        else:
            interval = max(2, round(interval * 1.2))
        repetitions += 1

    elif rating == 2:
        # Good — solid recall, standard SM-2 progression
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    else:
        # Easy (3) — effortless, boost the interval with extra multiplier
        if repetitions == 0:
            interval = 4        # skip ahead: 4 days instead of 1
        elif repetitions == 1:
            interval = 10       # skip ahead: 10 days instead of 6
        else:
            interval = round(interval * ease_factor * 1.3)  # 30% bonus
        repetitions += 1

    due_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    due_date = due_date + timedelta(days=interval)

    return SM2Output(
        ease_factor=ease_factor,
        interval=interval,
        repetitions=repetitions,
        due_date=due_date,
    )


def preview_intervals(ease_factor: float, interval: int, repetitions: int) -> dict[int, int]:
    """
    Returns what the next interval WOULD be for each possible rating (0–3).
    Used by the study page to show "next in X days" preview labels.
    """
    return {
        rating: calculate_sm2(SM2Input(
            ease_factor=ease_factor,
            interval=interval,
            repetitions=repetitions,
            rating=rating,
        )).interval
        for rating in range(4)
    }
