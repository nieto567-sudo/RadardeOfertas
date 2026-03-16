"""
Publication cooldown service.

Prevents the same product from being re-published within a configurable
time window (PUBLICATION_COOLDOWN_HOURS).  This is the primary anti-spam
guard that ensures the channel never floods users with duplicate deals.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, Publication


def is_on_cooldown(db: Session, product_id: int) -> bool:
    """
    Return *True* if this product was successfully published within the last
    ``PUBLICATION_COOLDOWN_HOURS``, meaning we should skip publishing again.
    """
    hours = settings.PUBLICATION_COOLDOWN_HOURS
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    recent = (
        db.query(Publication)
        .join(Offer, Publication.offer_id == Offer.id)
        .filter(
            Offer.product_id == product_id,
            Publication.success.is_(True),
            Publication.sent_at >= cutoff,
        )
        .first()
    )
    return recent is not None
