"""
Liverpool Mexico scraper (liverpool.com.mx).
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "laptop",
    "televisión",
    "smartphone",
    "tablet",
    "perfume",
    "cafetera",
    "consola",
]


class LiverpoolScraper(BaseScraper):
    """Scraper for Liverpool Mexico.

    Search URL pattern: https://www.liverpool.com.mx/tienda?s=<query>
    Example: https://www.liverpool.com.mx/tienda?s=celulares
    """

    store_name = "liverpool"
    BASE_URL = "https://www.liverpool.com.mx"
    SEARCH_URL = "https://www.liverpool.com.mx/tienda"

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._scrape_search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[liverpool] Error scraping '%s': %s", query, exc)
        return products

    def _scrape_search(self, query: str) -> list[ProductData]:
        params = {"s": query}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []

        cards = soup.select(
            "article[data-product-id], "
            "div[class*='product-card'], "
            "li[class*='product-item']"
        )

        for card in cards:
            product_id = (
                card.get("data-product-id")
                or card.get("data-sku")
                or card.get("data-id", "")
            )
            if not product_id:
                product_id = card.get("id", "")
            if not product_id:
                continue

            name_tag = card.select_one(
                "[class*='product-name'], [class*='ProductTitle'], h2, h3"
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            price_tag = card.select_one(
                "[class*='price'], [class*='Price'], [itemprop='price']"
            )
            if not price_tag:
                continue
            price = self.clean_price(price_tag.get_text(strip=True))
            if price is None:
                continue

            link_tag = card.select_one("a[href]")
            href = link_tag["href"] if link_tag else ""
            url = (
                "https://www.liverpool.com.mx" + href
                if href.startswith("/")
                else href
            )

            img_tag = card.select_one("img")
            image_url = None
            if img_tag:
                image_url = img_tag.get("src") or img_tag.get("data-src")

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=url,
                    store=self.store_name,
                    external_id=str(product_id),
                    available=True,
                    category=query,
                    image_url=image_url,
                )
            )

        logger.info("[liverpool] Found %d products for '%s'", len(results), query)
        return results
