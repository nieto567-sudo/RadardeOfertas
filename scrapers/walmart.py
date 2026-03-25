"""
Walmart Mexico scraper (walmart.com.mx).
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

SEARCH_API = "https://www.walmart.com.mx/api/2/page"

DEFAULT_QUERIES = [
    "laptop",
    "televisión",
    "smartphone",
    "tablet",
    "cafetera",
    "licuadora",
    "consola",
]


class WalmartScraper(BaseScraper):
    """Scraper for Walmart Mexico.

    Uses text search as the primary approach:
      https://www.walmart.com.mx/search?q=<query>

    Note: the platform also exposes category browse URLs of the form:
      https://www.walmart.com.mx/browse/<query>/destacados-<query>/
      lo-mas-vendido-<query>/264800_310034_310035?...
    These contain hard-coded department IDs and are therefore not suitable for
    generic keyword searches; text search is used as the general fallback.
    """

    store_name = "walmart"
    SEARCH_URL = "https://www.walmart.com.mx/search"

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._scrape_search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[walmart] Error scraping '%s': %s", query, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _scrape_search(self, query: str) -> list[ProductData]:
        params = {"q": query}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []

        # Walmart MX renders product cards with data attributes in the HTML
        cards = soup.select("article[data-id]") or soup.select(
            "div[class*='product-item']"
        )

        for card in cards:
            product_id = card.get("data-id") or card.get("data-sku", "")
            if not product_id:
                continue

            name_tag = card.select_one("[class*='product-name'], [class*='ProductName']")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            price_tag = card.select_one(
                "[class*='price-characteristic'], [class*='ProductPrice'], "
                "span[class*='price']"
            )
            if not price_tag:
                continue
            price = self.clean_price(price_tag.get_text(strip=True))
            if price is None:
                continue

            link_tag = card.select_one("a[href]")
            relative = link_tag["href"] if link_tag else ""
            url = (
                "https://www.walmart.com.mx" + relative
                if relative.startswith("/")
                else relative
            )

            img_tag = card.select_one("img")
            image_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

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

        logger.info("[walmart] Found %d products for '%s'", len(results), query)
        return results
