"""
Central scraper registry.

Usage::

    from scrapers.manager import ScraperManager

    manager = ScraperManager()
    all_products = manager.run_all()
"""
from __future__ import annotations

import logging
import time
from typing import Type

from scrapers.base import BaseScraper, ProductData
from scrapers.amazon import AmazonScraper
from scrapers.mercadolibre import MercadoLibreScraper
from scrapers.walmart import WalmartScraper
from scrapers.liverpool import LiverpoolScraper
from scrapers.bodega_aurrera import BodegaAurreraScraper
from scrapers.retailers_mx import (
    CostcoScraper,
    CoppelScraper,
    ElektraScraper,
    SearsScraper,
    SanbornsScraper,
    SamsClubScraper,
    OfficeDepotScraper,
    OfficeMaxScraper,
    SorianaScraper,
)
from scrapers.tech_stores import (
    CyberpuertaScraper,
    DDTechScraper,
    PCELScraper,
    IntercomprasScraper,
    GameplanetScraper,
    ClaroShopScraper,
)
from services.circuit_breaker import CircuitBreaker
from services.metrics import SCRAPE_PRODUCTS, SCRAPE_ERRORS, SCRAPE_DURATION

logger = logging.getLogger(__name__)

# All registered scraper classes
ALL_SCRAPERS: list[Type[BaseScraper]] = [
    # Marketplaces
    AmazonScraper,
    MercadoLibreScraper,
    # Mexican retailers
    WalmartScraper,
    BodegaAurreraScraper,
    LiverpoolScraper,
    CostcoScraper,
    CoppelScraper,
    ElektraScraper,
    SearsScraper,
    SanbornsScraper,
    SamsClubScraper,
    OfficeDepotScraper,
    OfficeMaxScraper,
    SorianaScraper,
    # Tech stores
    CyberpuertaScraper,
    DDTechScraper,
    PCELScraper,
    IntercomprasScraper,
    GameplanetScraper,
    ClaroShopScraper,
]


class ScraperManager:
    """Instantiates and runs all registered scrapers."""

    def __init__(self, scraper_classes: list[Type[BaseScraper]] | None = None) -> None:
        self.scraper_classes = scraper_classes or ALL_SCRAPERS

    def run_all(self) -> list[ProductData]:
        """Run every scraper and return the combined list of products."""
        all_products: list[ProductData] = []
        for cls in self.scraper_classes:
            store = getattr(cls, "store_name", cls.__name__)
            cb = CircuitBreaker(store)
            if cb.is_open():
                logger.info("[manager] %s skipped — circuit breaker OPEN", store)
                SCRAPE_ERRORS.labels(store=store).inc()
                continue
            t0 = time.monotonic()
            try:
                scraper = cls()
                products = scraper.scrape()
                elapsed = time.monotonic() - t0
                SCRAPE_DURATION.labels(store=store).observe(elapsed)
                SCRAPE_PRODUCTS.labels(store=store).inc(len(products))
                logger.info(
                    "[manager] %s returned %d products in %.1fs",
                    cls.__name__,
                    len(products),
                    elapsed,
                )
                cb.record_success()
                all_products.extend(products)
            except Exception as exc:  # pylint: disable=broad-except
                elapsed = time.monotonic() - t0
                SCRAPE_DURATION.labels(store=store).observe(elapsed)
                SCRAPE_ERRORS.labels(store=store).inc()
                cb.record_failure()
                logger.error("[manager] %s failed: %s", cls.__name__, exc)
        return all_products

    def run_store(self, store_name: str) -> list[ProductData]:
        """Run the scraper for a single store by its store_name."""
        for cls in self.scraper_classes:
            if cls.store_name == store_name:  # type: ignore[attr-defined]
                cb = CircuitBreaker(store_name)
                if cb.is_open():
                    logger.info(
                        "[manager] %s skipped — circuit breaker OPEN", store_name
                    )
                    return []
                t0 = time.monotonic()
                try:
                    products = cls().scrape()
                    SCRAPE_DURATION.labels(store=store_name).observe(
                        time.monotonic() - t0
                    )
                    SCRAPE_PRODUCTS.labels(store=store_name).inc(len(products))
                    cb.record_success()
                    return products
                except Exception as exc:  # pylint: disable=broad-except
                    SCRAPE_DURATION.labels(store=store_name).observe(
                        time.monotonic() - t0
                    )
                    SCRAPE_ERRORS.labels(store=store_name).inc()
                    cb.record_failure()
                    logger.error("[manager] %s failed: %s", cls.__name__, exc)
                    return []
        logger.warning("[manager] No scraper found for store '%s'", store_name)
        return []
