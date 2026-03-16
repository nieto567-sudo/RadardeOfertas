"""
Price history sparkline generator.

Generates a compact text-based sparkline (▁▂▃▄▅▆▇█) showing the price
trajectory of a product over time, and detects whether the current price
is the all-time historical minimum.

Usage
-----
::

    from services.price_sparkline import get_sparkline, is_all_time_low

    line = get_sparkline(db, product_id=42)
    # → "▃▂▁▂▄▆▇█▄▂▁▁"

    low = is_all_time_low(db, product_id=42, current_price=299.0)
    # → True
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from database.models import PriceHistory

_BLOCKS = "▁▂▃▄▅▆▇█"

# Minimum observations required to generate a sparkline.
_MIN_POINTS = 3
# Maximum character width of the sparkline in the message.
_MAX_SPARKLINE_WIDTH = 14


def get_sparkline(
    db: Session,
    product_id: int,
    max_points: int = _MAX_SPARKLINE_WIDTH,
) -> Optional[str]:
    """
    Return a sparkline string for the price history of *product_id*.

    Returns ``None`` when there are fewer than ``_MIN_POINTS`` data points.
    The sparkline is built from evenly-sampled price observations, oldest
    on the left and newest on the right.
    """
    rows = (
        db.query(PriceHistory.price)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at)
        .all()
    )
    prices = [r[0] for r in rows]

    if len(prices) < _MIN_POINTS:
        return None

    # Downsample to max_points using uniform sampling
    if len(prices) > max_points:
        step = len(prices) / max_points
        prices = [prices[int(i * step)] for i in range(max_points)]

    min_p = min(prices)
    max_p = max(prices)

    if max_p == min_p:
        # All prices the same — flat sparkline
        return _BLOCKS[0] * len(prices)

    def _to_block(p: float) -> str:
        idx = int((p - min_p) / (max_p - min_p) * (len(_BLOCKS) - 1))
        return _BLOCKS[max(0, min(len(_BLOCKS) - 1, idx))]

    return "".join(_to_block(p) for p in prices)


def is_all_time_low(
    db: Session,
    product_id: int,
    current_price: float,
) -> bool:
    """
    Return ``True`` if *current_price* is at or below the historical minimum
    price ever recorded for *product_id*.

    Uses a 1-cent tolerance to handle floating-point imprecision.
    """
    rows = (
        db.query(PriceHistory.price)
        .filter(PriceHistory.product_id == product_id)
        .all()
    )
    prices = [r[0] for r in rows]
    if not prices:
        return False
    return current_price <= min(prices) + 0.01
