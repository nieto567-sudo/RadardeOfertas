"""
High-level offer processing pipeline.

Ties together:
  1. PriceAnalyzer     – upsert product + detect deal
  2. ProductClassifier – auto-assign category when missing
  3. OfferFilter       – discard garbage / low-quality deals
  4. OfferScorer       – calculate score (0–100)
  5. ViralDetector     – calculate viral potential (0–20)
  6. ResaleDetector    – detect resale opportunities (0–10)
  7. affiliate         – convert URL to affiliate link (with UTM + Bitly)
  8. RevenueTracker    – persist estimated commission
  9. DailyCap check    – enforce MAX_DAILY_PUBLICATIONS per 24 h
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, OfferStatus, Publication
from scrapers.base import ProductData
from services.affiliate import get_affiliate_url, shorten_url
from services.cooldown import is_on_cooldown
from services.offer_filter import passes_quality_filter
from services.offer_scorer import OfferScorer
from services.price_analyzer import PriceAnalyzer
from services.product_classifier import update_product_category
from services.resale_detector import detect_resale_opportunity
from services.revenue_tracker import record_revenue
from services.viral_detector import calculate_viral_score

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

            # Auto-classify product when category is missing
            update_product_category(offer.product, data)

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

            # Quality / garbage filter: discard tiny or low-value deals
            try:
                quality = passes_quality_filter(offer)
                if not quality.passed:
                    offer.status = OfferStatus.DISCARDED
                    self.db.commit()
                    logger.debug(
                        "Offer %d discarded by quality filter: %s",
                        offer.id,
                        quality.reason,
                    )
                    return None
            except Exception as exc:  # pylint: disable=broad-except
                # Non-fatal: continue pipeline when filter cannot evaluate
                logger.debug("Quality filter skipped (error): %s", exc)

            score = self.scorer.score(offer)
            if score < settings.MIN_PUBLISH_SCORE:
                offer.status = OfferStatus.DISCARDED
                self.db.commit()
                return None

            # Supplementary scores (stored for analytics + message display)
            try:
                offer.viral_score = calculate_viral_score(offer)
                resale = detect_resale_opportunity(offer)
                offer.resale_score = resale.score
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Supplementary scores skipped (error): %s", exc)

            # Publication deadline: discard if still pending after window
            try:
                offer.publication_deadline = datetime.now(tz=timezone.utc) + timedelta(
                    minutes=settings.PUBLICATION_WINDOW_MINUTES
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Publication deadline skipped (error): %s", exc)

            # Generate affiliate link (includes UTM params and optional Bitly shortening)
            affiliate_url = get_affiliate_url(data.url, data.store)
            offer.affiliate_url = affiliate_url

            # Persist estimated revenue record
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
                "Offer %d ready (score=%d viral=%d resale=%d)",
                offer.id,
                score,
                offer.viral_score,
                offer.resale_score,
            )
            return offer
        except Exception as exc:  # pylint: disable=broad-except
            self.db.rollback()
            logger.error("OfferProcessor.process failed for %s: %s", data.name, exc)
            return None


def get_daily_publication_count(db: Session) -> int:
    """
    Return how many offers have been successfully published in the last 24 h.

    Used to enforce ``MAX_DAILY_PUBLICATIONS``.
    """
    from database.models import Publication as Pub

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    return (
        db.query(Pub)
        .filter(
            Pub.success.is_(True),
            Pub.sent_at >= cutoff,
        )
        .count()
    )
