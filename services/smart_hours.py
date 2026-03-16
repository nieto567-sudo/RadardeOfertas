"""
Smart publishing hours for Mexico.

Offers are only published during peak engagement windows in Mexico City
(UTC-6, CST — no automatic DST adjustment; UTC-5 during summer has only a
one-hour effect which is acceptable for approximate scheduling).

Default peak windows (Mexico City local time)
---------------------------------------------
* Morning:   07:00 – 10:00
* Afternoon: 12:00 – 15:00
* Evening:   19:00 – 23:00

All windows and the feature itself can be overridden via environment
variables.  Set ``SMART_HOURS_ENABLED=false`` to publish 24/7.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import settings

# Fixed UTC-6 offset (Mexico City winter / CST).
_MX_UTC_OFFSET = timedelta(hours=-6)


def is_good_time_to_publish(now: datetime | None = None) -> bool:
    """
    Return ``True`` if *now* falls inside a peak publishing window for Mexico.

    Parameters
    ----------
    now : datetime, optional
        UTC-aware datetime to evaluate.  Defaults to the current UTC time.
    """
    if not settings.SMART_HOURS_ENABLED:
        return True

    now_utc = now if now is not None else datetime.now(tz=timezone.utc)
    # Convert to approximate Mexico City local time
    mx_hour = (now_utc + _MX_UTC_OFFSET).hour

    return any(start <= mx_hour < end for start, end in _windows())


def minutes_until_next_window(now: datetime | None = None) -> int:
    """
    Return how many minutes remain until the next publishing window opens.

    Returns 0 when already inside a window (i.e. it is a good time now).
    """
    if not settings.SMART_HOURS_ENABLED:
        return 0

    now_utc = now if now is not None else datetime.now(tz=timezone.utc)
    mx_dt = now_utc + _MX_UTC_OFFSET
    current_minutes = mx_dt.hour * 60 + mx_dt.minute

    if any(start <= mx_dt.hour < end for start, end in _windows()):
        return 0

    candidates: list[int] = []
    for start, _ in _windows():
        start_m = start * 60
        diff = start_m - current_minutes
        if diff <= 0:
            diff += 1440  # wraps to next day
        candidates.append(diff)

    return min(candidates) if candidates else 0


# ── private ───────────────────────────────────────────────────────────────────


def _windows() -> list[tuple[int, int]]:
    """Return list of (start_hour_inclusive, end_hour_exclusive) pairs."""
    return [
        (settings.SMART_HOURS_MORNING_START, settings.SMART_HOURS_MORNING_END),
        (settings.SMART_HOURS_AFTERNOON_START, settings.SMART_HOURS_AFTERNOON_END),
        (settings.SMART_HOURS_EVENING_START, settings.SMART_HOURS_EVENING_END),
    ]
