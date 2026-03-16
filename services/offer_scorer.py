"""
Offer scoring engine.

Scores are in the range 0–100 and follow these bands:

    95–100  error de precio
    80–94   oferta excelente
    60–79   buena oferta
    < 60    descartada (not published)

Score components
----------------
* discount_score  – based on percentage discount (up to 60 pts)
* history_score   – penalty when there is little price history (up to 20 pts)
* rapid_drop_bonus – extra points for sudden price falls (up to 10 pts)
* popularity_score – based on number of price observations (up to 10 pts)
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from database.models import Offer, OfferType

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_SCORE_ERROR_MIN = 95
_SCORE_EXCELLENT_MIN = 80
_SCORE_GOOD_MIN = 60


class OfferScorer:
    """Computes and stores the score for an :class:`~database.models.Offer`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── public ────────────────────────────────────────────────────────────────

    def score(self, offer: Offer) -> int:
        """
        Calculate the score (0–100) for *offer*, persist it, and return it.
        """
        total = (
            self._discount_score(offer.discount_pct)
            + self._history_score(offer)
            + self._rapid_drop_bonus(offer)
            + self._popularity_score(offer)
        )
        # Clamp to [0, 100]
        total = max(0, min(100, total))
        offer.score = total
        logger.debug(
            "Scored offer %d: %d pts (discount=%.1f%% rapid=%s)",
            offer.id,
            total,
            offer.discount_pct,
            offer.rapid_drop,
        )
        return total

    # ── components ────────────────────────────────────────────────────────────

    @staticmethod
    def _discount_score(discount_pct: float) -> int:
        """
        0–60 pts based on discount percentage.
        Maps 0 % → 0 pts and 100 % → 60 pts (linear, capped).
        """
        return min(60, int(discount_pct * 0.6))

    def _history_score(self, offer: Offer) -> int:
        """
        0–20 pts based on how established the price history is.
        More observations → closer to 20 pts.
        """
        from database.models import PriceHistory  # local to avoid circular

        count = (
            self.db.query(PriceHistory)
            .filter(PriceHistory.product_id == offer.product_id)
            .count()
        )
        if count >= 30:
            return 20
        if count >= 10:
            return 15
        if count >= 5:
            return 10
        if count >= 2:
            return 5
        return 0

    @staticmethod
    def _rapid_drop_bonus(offer: Offer) -> int:
        """10 bonus points when a rapid price drop was detected."""
        return 10 if offer.rapid_drop else 0

    def _popularity_score(self, offer: Offer) -> int:
        """
        0–10 pts.  We use the total number of price observations as a
        rough proxy for product popularity (more monitoring → more popular).
        """
        from database.models import PriceHistory  # local to avoid circular

        count = (
            self.db.query(PriceHistory)
            .filter(PriceHistory.product_id == offer.product_id)
            .count()
        )
        if count >= 50:
            return 10
        if count >= 20:
            return 7
        if count >= 10:
            return 5
        return 2

    # ── classification helpers ────────────────────────────────────────────────

    @staticmethod
    def classify_score(score: int) -> str:
        if score >= _SCORE_ERROR_MIN:
            return "error de precio"
        if score >= _SCORE_EXCELLENT_MIN:
            return "oferta excelente"
        if score >= _SCORE_GOOD_MIN:
            return "buena oferta"
        return "regular"
