"""
Central scraper registry.

Usage::

    from scrapers.manager import ScraperManager

    manager = ScraperManager()
    all_products = manager.run_all()
"""
from __future__ import annotations

import logging
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
from scrapers.international import (
    AliExpressScraper,
    eBayScraper,
    NeweggScraper,
    BanggoodScraper,
    GearbestScraper,
)

logger = logging.getLogger(__name__)

# All registered scraper classes
ALL_SCRAPERS: list[Type[BaseScraper]] = [
    # Marketplaces
    AmazonScraper,
    MercadoLibreScraper,
    AliExpressScraper,
    eBayScraper,
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
    # International
    NeweggScraper,
    BanggoodScraper,
    GearbestScraper,
]


class ScraperManager:
    """Instantiates and runs all registered scrapers."""

    def __init__(self, scraper_classes: list[Type[BaseScraper]] | None = None) -> None:
        self.scraper_classes = scraper_classes or ALL_SCRAPERS

    def run_all(self) -> list[ProductData]:
        """Run every scraper and return the combined list of products."""
        all_products: list[ProductData] = []
        for cls in self.scraper_classes:
            try:
                scraper = cls()
                products = scraper.scrape()
                logger.info(
                    "[manager] %s returned %d products", cls.__name__, len(products)
                )
                all_products.extend(products)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[manager] %s failed: %s", cls.__name__, exc)
        return all_products

    def run_store(self, store_name: str) -> list[ProductData]:
        """Run the scraper for a single store by its store_name."""
        for cls in self.scraper_classes:
            if cls.store_name == store_name:  # type: ignore[attr-defined]
                try:
                    return cls().scrape()
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("[manager] %s failed: %s", cls.__name__, exc)
                    return []
        logger.warning("[manager] No scraper found for store '%s'", store_name)
        return []
