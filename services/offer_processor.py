"""
High-level offer processing pipeline.

Ties together:
  1. PriceAnalyzer  – upsert product + detect deal
  2. OfferScorer    – calculate score
  3. affiliate      – convert URL to affiliate link (with UTM + Bitly)
  4. RevenueTracker – persist estimated commission
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, OfferStatus
from scrapers.base import ProductData
from services.affiliate import get_affiliate_url, shorten_url
from services.cooldown import is_on_cooldown
from services.offer_scorer import OfferScorer
from services.price_analyzer import PriceAnalyzer
from services.revenue_tracker import record_revenue

logger = logging.getLogger(__name__)


class OfferProcessor:
    """Process a single :class:`ProductData` and return a publishable offer."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.analyzer = PriceAnalyzer(db)
        self.scorer = OfferScorer(db)

    def process(self, data: ProductData) -> Optional[Offer]:
        """
        Full pipeline for one product observation.

        Returns the :class:`Offer` if it meets the minimum publication score,
        otherwise returns *None*.
        """
        try:
            offer = self.analyzer.process(data)
            if offer is None:
                return None

            # Anti-spam: skip if this product was already published recently
            if is_on_cooldown(self.db, offer.product_id):
                offer.status = OfferStatus.DISCARDED
                self.db.commit()
                logger.debug(
                    "Offer %d skipped — product %d is on cooldown",
                    offer.id,
                    offer.product_id,
                )
                return None

            score = self.scorer.score(offer)
            if score < settings.MIN_PUBLISH_SCORE:
                offer.status = OfferStatus.DISCARDED
                self.db.commit()
                return None

            # Generate affiliate link (includes UTM params and optional Bitly shortening)
            affiliate_url = get_affiliate_url(data.url, data.store)
            offer.affiliate_url = affiliate_url

            # Persist estimated revenue record
            # Use the Bitly short URL if the affiliate URL was already shortened
            short_url = affiliate_url if "bit.ly" in affiliate_url else None
            record_revenue(
                self.db,
                offer,
                store=data.store,
                price=data.price,
                short_url=short_url,
            )

            self.db.commit()
            logger.info(
                "Offer %d ready for publication (score=%d)", offer.id, score
            )
            return offer
        except Exception as exc:  # pylint: disable=broad-except
            self.db.rollback()
            logger.error("OfferProcessor.process failed for %s: %s", data.name, exc)
            return None
