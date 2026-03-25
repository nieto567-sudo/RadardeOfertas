"""
Bodega Aurrerá scraper (bodegaaurrera.com.mx).

Bodega Aurrerá shares Walmart's commerce platform so the HTML structure
is very similar.
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
    "cafetera",
    "licuadora",
    "refrigerador",
]


class BodegaAurreraScraper(BaseScraper):
    """Scraper for Bodega Aurrerá Mexico.

    Uses text search as the primary approach:
      https://www.bodegaaurrera.com.mx/search?q=<query>

    Note: the platform also supports category browse URLs of the form:
      https://www.bodegaaurrera.com.mx/browse/<query>/destacados-<query>/
      destacados-<query>/264800_310034_310035?redirectQuery=<query>&search_redirect=true
    These contain hard-coded department IDs and are therefore not suitable for
    generic keyword searches; text search is used as the general fallback.
    """

    store_name = "bodega_aurrera"
    SEARCH_URL = "https://www.bodegaaurrera.com.mx/search"

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._scrape_search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[bodega_aurrera] Error scraping '%s': %s", query, exc)
        return products

    def _scrape_search(self, query: str) -> list[ProductData]:
        params = {"q": query}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []

        cards = soup.select("article[data-id], div[class*='product-item']")

        for card in cards:
            product_id = card.get("data-id") or card.get("data-sku", "")
            if not product_id:
                continue

            name_tag = card.select_one(
                "[class*='product-name'], [class*='ProductName']"
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            price_tag = card.select_one(
                "[class*='price-characteristic'], span[class*='price']"
            )
            if not price_tag:
                continue
            price = self.clean_price(price_tag.get_text(strip=True))
            if price is None:
                continue

            link_tag = card.select_one("a[href]")
            relative = link_tag["href"] if link_tag else ""
            url = (
                "https://www.bodegaaurrera.com.mx" + relative
                if relative.startswith("/")
                else relative
            )

            img_tag = card.select_one("img")
            image_url = (
                img_tag.get("src") or img_tag.get("data-src") if img_tag else None
            )

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

        logger.info(
            "[bodega_aurrera] Found %d products for '%s'", len(results), query
        )
        return results
