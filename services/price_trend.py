"""
Price trend service.

Uses a simple linear regression over the most recent price observations to
determine whether a product's price is trending up, down, or sideways.

Return values
-------------
``"up"``    – price is trending up   (slope > +1 % of mean per step)
``"down"``  – price is trending down (slope < -1 % of mean per step)
``"flat"``  – price is roughly stable
``None``    – not enough data points to compute a trend
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import PriceHistory


# ── public API ────────────────────────────────────────────────────────────────


def get_price_trend(db: Session, product_id: int) -> Optional[str]:
    """
    Return the price trend (``"up"``, ``"down"``, or ``"flat"``) for
    *product_id*, or ``None`` when there is insufficient history.
    """
    rows = (
        db.query(PriceHistory.price)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at)
        .all()
    )
    prices = [r[0] for r in rows]

    min_pts = settings.TREND_MIN_POINTS
    if len(prices) < min_pts:
        return None

    # Use last min_pts * 2 points to focus on recent trend without too much noise
    recent = prices[-(min_pts * 2):]
    slope = _linear_slope(recent)
    mean_price = sum(recent) / len(recent)

    if mean_price == 0:
        return None

    # Classify: if slope exceeds ±1 % of mean per observation we call it a trend
    threshold = mean_price * 0.01
    if slope > threshold:
        return "up"
    if slope < -threshold:
        return "down"
    return "flat"


def trend_emoji(trend: Optional[str]) -> str:
    """Return a display emoji for *trend*."""
    return {
        "up": "📈",
        "down": "📉",
        "flat": "➡️",
    }.get(trend or "", "")


# ── helpers ───────────────────────────────────────────────────────────────────


def _linear_slope(values: list[float]) -> float:
    """
    Compute the slope of the best-fit line through *values* using ordinary
    least squares (no external libraries required).
    """
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0
    return numerator / denominator
