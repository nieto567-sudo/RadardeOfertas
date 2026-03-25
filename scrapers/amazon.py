"""
Amazon Mexico scraper.

Scrapes the Amazon Mexico search results page to find products.
For higher volume / more reliable access, consider using the
Product Advertising API v5 (set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY,
and AMAZON_PARTNER_TAG environment variables).
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

# Default search terms to monitor on Amazon Mexico
DEFAULT_SEARCH_TERMS = [
    "laptop",
    "smartphone",
    "televisión",
    "auriculares",
    "tablet",
    "consola videojuegos",
    "cafetera",
    "aspiradora robot",
]


class AmazonScraper(BaseScraper):
    """Scraper for Amazon Mexico (amazon.com.mx).

    Search URL pattern: https://www.amazon.com.mx/s?k=<query>
    Example: https://www.amazon.com.mx/s?k=celulares

    Note: Amazon MX aggressively blocks datacenter IPs (Railway/cloud). If you
    see persistent 503 errors, consider adding residential proxies
    (HTTP_PROXY / HTTPS_PROXY env vars) or reducing request frequency.
    For higher reliability and volume, use the Product Advertising API v5
    (set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, and AMAZON_PARTNER_TAG env vars).
    """

    store_name = "amazon"
    BASE_URL = "https://www.amazon.com.mx"
    SEARCH_URL = "https://www.amazon.com.mx/s"

    def __init__(self) -> None:
        super().__init__()
        self.search_terms = DEFAULT_SEARCH_TERMS

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for term in self.search_terms:
            try:
                products.extend(self._scrape_search(term))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[amazon] Error scraping '%s': %s", term, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _scrape_search(self, query: str) -> list[ProductData]:
        """Scrape one search-results page for *query* and return products."""
        params = {"k": query, "i": "aps"}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []
        cards = soup.select("div[data-asin][data-component-type='s-search-result']")
        for card in cards:
            asin = card.get("data-asin", "").strip()
            if not asin:
                continue

            # Product name
            name_tag = card.select_one("h2 a span")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            # Price
            whole = card.select_one("span.a-price-whole")
            fraction = card.select_one("span.a-price-fraction")
            if not whole:
                continue
            price_str = whole.get_text(strip=True).rstrip(".")
            if fraction:
                price_str += "." + fraction.get_text(strip=True)
            price = self.clean_price(price_str)
            if price is None:
                continue

            # URL
            link_tag = card.select_one("h2 a")
            relative_url = link_tag["href"] if link_tag else f"/dp/{asin}"
            url = self.BASE_URL + relative_url.split("?")[0]

            # Image
            img_tag = card.select_one("img.s-image")
            image_url = img_tag["src"] if img_tag else None

            # Category from the search term as a best-effort
            category = query

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=url,
                    store=self.store_name,
                    external_id=asin,
                    available=True,
                    category=category,
                    image_url=image_url,
                )
            )

        logger.info("[amazon] Found %d products for '%s'", len(results), query)
        return results
