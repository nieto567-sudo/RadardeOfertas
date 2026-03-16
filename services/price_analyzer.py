"""
Price analysis service.

Responsibilities
----------------
* Upsert a product and record the current price in price_history.
* Detect offer type (error / excellent / good / regular) by comparing the
  current price with the rolling average.
* Detect rapid price drops within a configurable time window.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, OfferStatus, OfferType, PriceHistory, Product
from scrapers.base import ProductData

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """
    Analyses price changes for a single product.

    All database operations are performed within the session provided at
    construction time.  The caller is responsible for committing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── public API ────────────────────────────────────────────────────────────

    def process(self, data: ProductData) -> Optional[Offer]:
        """
        Upsert the product, record the price, and return an :class:`Offer` if
        a deal was detected.  Returns *None* when no interesting deal is found.
        """
        product = self._upsert_product(data)
        self._record_price(product, data.price, data.available)
        return self._analyse(product, data.price)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _upsert_product(self, data: ProductData) -> Product:
        """Insert or update the product row, return the ORM instance."""
        product = (
            self.db.query(Product)
            .filter_by(external_id=data.external_id, store=data.store)
            .first()
        )
        if product is None:
            product = Product(
                external_id=data.external_id,
                store=data.store,
                name=data.name,
                url=data.url,
                image_url=data.image_url,
                category=data.category,
                current_price=data.price,
                available=data.available,
            )
            self.db.add(product)
            self.db.flush()
            logger.debug("New product: %s (%s)", data.name, data.store)
        else:
            product.name = data.name
            product.url = data.url
            product.image_url = data.image_url
            product.category = data.category
            product.current_price = data.price
            product.available = data.available

        return product

    def _record_price(self, product: Product, price: float, available: bool) -> None:
        entry = PriceHistory(
            product_id=product.id,
            price=price,
            available=available,
        )
        self.db.add(entry)

    def _average_price(self, product: Product) -> Optional[float]:
        """Return the mean of all recorded prices (excluding the latest)."""
        prices = (
            self.db.query(PriceHistory.price)
            .filter(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.recorded_at)
            .all()
        )
        values = [p[0] for p in prices]
        if len(values) < 2:
            # Not enough data to compute a meaningful average
            return None
        # Exclude the most recent observation (which is the current price)
        return mean(values[:-1])

    def _detect_rapid_drop(self, product: Product, current_price: float) -> bool:
        """
        Return True if the price dropped by more than RAPID_DROP_THRESHOLD
        within the last RAPID_DROP_WINDOW_HOURS.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(
            hours=settings.RAPID_DROP_WINDOW_HOURS
        )
        recent = (
            self.db.query(PriceHistory.price)
            .filter(
                PriceHistory.product_id == product.id,
                PriceHistory.recorded_at >= cutoff,
            )
            .order_by(PriceHistory.recorded_at)
            .first()
        )
        if recent is None:
            return False
        oldest_price = recent[0]
        if oldest_price == 0:
            return False
        drop_pct = (oldest_price - current_price) / oldest_price
        return drop_pct >= settings.RAPID_DROP_THRESHOLD

    @staticmethod
    def _classify(ratio: float) -> OfferType:
        """Classify the offer type based on current/average price ratio."""
        if ratio <= settings.PRICE_ERROR_THRESHOLD:
            return OfferType.PRICE_ERROR
        if ratio <= settings.OFFER_EXCELLENT_THRESHOLD:
            return OfferType.EXCELLENT
        if ratio <= settings.OFFER_GOOD_THRESHOLD:
            return OfferType.GOOD
        return OfferType.REGULAR

    def _analyse(self, product: Product, current_price: float) -> Optional[Offer]:
        """
        Compare current price with historical average and create an
        :class:`Offer` row if the deal is at least 'good'.
        """
        avg = self._average_price(product)
        if avg is None or avg == 0:
            return None

        ratio = current_price / avg
        if ratio >= settings.OFFER_GOOD_THRESHOLD:
            # Not cheap enough to warrant an alert
            return None

        offer_type = self._classify(ratio)
        discount_pct = round((1 - ratio) * 100, 2)
        rapid_drop = self._detect_rapid_drop(product, current_price)

        offer = Offer(
            product_id=product.id,
            current_price=current_price,
            original_price=avg,
            discount_pct=discount_pct,
            score=0,  # will be set by the scorer
            offer_type=offer_type,
            status=OfferStatus.PENDING,
            rapid_drop=rapid_drop,
        )
        self.db.add(offer)
        self.db.flush()

        logger.info(
            "Offer detected: %s | current=%.2f avg=%.2f discount=%.1f%% rapid=%s",
            product.name,
            current_price,
            avg,
            discount_pct,
            rapid_drop,
        )
        return offer
