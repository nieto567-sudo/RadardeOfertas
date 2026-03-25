"""
The Home Depot Mexico scraper (homedepot.com.mx).

Search URL pattern: https://www.homedepot.com.mx/s/<query>
Example: https://www.homedepot.com.mx/s/refrigerador
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "refrigerador",
    "lavadora",
    "herramienta",
    "pintura",
    "taladro",
    "cafetera",
    "ventilador",
]


class HomeDepotScraper(BaseScraper):
    """Scraper for The Home Depot Mexico.

    The search URL embeds the query directly in the path:
      https://www.homedepot.com.mx/s/<query>
    Example: https://www.homedepot.com.mx/s/refrigerador
    """

    store_name = "homedepot"
    BASE_URL = "https://www.homedepot.com.mx"
    SEARCH_BASE = "https://www.homedepot.com.mx/s"

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    @classmethod
    def build_search_url(cls, query: str) -> str:
        """Return the search URL for *query*.

        Example::

            >>> HomeDepotScraper.build_search_url("refrigerador")
            'https://www.homedepot.com.mx/s/refrigerador'
        """
        return f"{cls.SEARCH_BASE}/{quote(query, safe='')}"

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._scrape_search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[homedepot] Error scraping '%s': %s", query, exc)
        return products

    def _scrape_search(self, query: str) -> list[ProductData]:
        url = self.build_search_url(query)
        try:
            soup = self.soup(url)
        except requests.RequestException:
            return []

        results: list[ProductData] = []

        cards = soup.select(
            "div[class*='product-tile'], "
            "div[class*='ProductCard'], "
            "li[class*='product-item']"
        )

        for idx, card in enumerate(cards):
            name_tag = card.select_one(
                "[class*='product-title'], [class*='ProductTitle'], h2, h3"
            )
            price_tag = card.select_one(
                "[class*='price'], [class*='Price'], [itemprop='price']"
            )
            if not name_tag or not price_tag:
                continue

            name = name_tag.get_text(strip=True)
            price = self.clean_price(price_tag.get_text(strip=True))
            if not name or price is None:
                continue

            link_tag = card.select_one("a[href]")
            href = link_tag["href"] if link_tag else ""
            product_url = (
                self.BASE_URL + href if href.startswith("/") else href
            ) or url

            img_tag = card.select_one("img")
            image_url = (
                img_tag.get("src") or img_tag.get("data-src") if img_tag else None
            )

            product_id = (
                card.get("data-product-id")
                or card.get("data-sku")
                or card.get("data-id")
                or f"homedepot_{query}_{idx}"
            )

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=product_url,
                    store=self.store_name,
                    external_id=str(product_id),
                    available=True,
                    category=query,
                    image_url=image_url,
                )
            )

        logger.info("[homedepot] Found %d products for '%s'", len(results), query)
        return results
