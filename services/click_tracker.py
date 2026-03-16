"""
Click and purchase event tracker.

Records engagement events (clicks, confirmed purchases) for published
offers and provides aggregated analytics queries for the bot's
``/estadisticas`` command.

Usage
-----
::

    # Record a click
    event = record_click(db, offer_id=42, source="telegram")
    db.commit()

    # Record a confirmed purchase / conversion
    event = record_purchase(db, offer_id=42, revenue_mxn=45.00)
    db.commit()

    # Query per-offer stats
    stats = get_offer_stats(db, offer_id=42)
    # → {"offer_id": 42, "clicks": 17, "purchases": 3}

    # Query global stats for the last 7 days
    global_stats = get_global_stats(db, days=7)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import OfferClickEvent, OfferPurchaseEvent


def record_click(
    db: Session, offer_id: int, source: str = "telegram"
) -> OfferClickEvent:
    """
    Persist one click event for *offer_id*.

    Parameters
    ----------
    db : Session
    offer_id : int
        The offer whose link was followed.
    source : str
        Origin of the click (e.g. ``"telegram"``, ``"web"``).
    """
    event = OfferClickEvent(offer_id=offer_id, source=source)
    db.add(event)
    return event


def record_purchase(
    db: Session,
    offer_id: int,
    revenue_mxn: float = 0.0,
    source: str = "telegram",
) -> OfferPurchaseEvent:
    """
    Persist one confirmed purchase / conversion for *offer_id*.

    Parameters
    ----------
    db : Session
    offer_id : int
    revenue_mxn : float
        Actual or estimated commission earned in MXN.
    source : str
        Origin channel of the conversion.
    """
    event = OfferPurchaseEvent(
        offer_id=offer_id,
        revenue_mxn=revenue_mxn,
        source=source,
    )
    db.add(event)
    return event


def get_offer_stats(db: Session, offer_id: int) -> dict:
    """Return click and purchase counts for a single offer."""
    clicks = (
        db.query(OfferClickEvent)
        .filter(OfferClickEvent.offer_id == offer_id)
        .count()
    )
    purchases = (
        db.query(OfferPurchaseEvent)
        .filter(OfferPurchaseEvent.offer_id == offer_id)
        .count()
    )
    return {"offer_id": offer_id, "clicks": clicks, "purchases": purchases}


def get_global_stats(db: Session, days: int = 7) -> dict:
    """
    Return aggregated click / purchase statistics for the last *days* days.

    Returns
    -------
    dict
        Keys: ``period_days``, ``total_clicks``, ``total_purchases``,
        ``conversion_rate`` (float 0–1).
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    total_clicks: int = (
        db.query(OfferClickEvent)
        .filter(OfferClickEvent.clicked_at >= cutoff)
        .count()
    )
    total_purchases: int = (
        db.query(OfferPurchaseEvent)
        .filter(OfferPurchaseEvent.purchased_at >= cutoff)
        .count()
    )

    return {
        "period_days": days,
        "total_clicks": total_clicks,
        "total_purchases": total_purchases,
        "conversion_rate": (
            total_purchases / total_clicks if total_clicks > 0 else 0.0
        ),
    }
