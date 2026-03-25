"""
MercadoLibre Mexico scraper.

Uses the public MercadoLibre Search API (no auth required for basic search).
API docs: https://developers.mercadolibre.com.mx/
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

# Categories / queries to monitor
DEFAULT_QUERIES = [
    "laptop",
    "smartphone",
    "televisión",
    "tablet",
    "consola",
    "auriculares",
    "cafetera",
    "refrigerador",
]

API_SEARCH = "https://api.mercadolibre.com/sites/MLM/search"
API_ITEM = "https://api.mercadolibre.com/items/{item_id}"


class MercadoLibreScraper(BaseScraper):
    """Scraper for MercadoLibre Mexico using their public Search API.

    Uses the public REST API (no auth required):
      https://api.mercadolibre.com/sites/MLM/search?q=<query>

    Website search URL for reference (not used directly):
      https://listado.mercadolibre.com.mx/<query>#D[A:<query>]
    Example: https://listado.mercadolibre.com.mx/celulares#D[A:celulares]
    """

    store_name = "mercadolibre"

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[mercadolibre] Error searching '%s': %s", query, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _search(self, query: str, limit: int = 50) -> list[ProductData]:
        params = {"q": query, "limit": limit, "site_id": "MLM"}
        try:
            resp = self.get(API_SEARCH, params=params)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[mercadolibre] Search '%s' failed: %s", query, exc)
            return []

        results: list[ProductData] = []
        for item in data.get("results", []):
            item_id = item.get("id", "")
            name = item.get("title", "")
            price = item.get("price")
            url = item.get("permalink", "")
            thumbnail = item.get("thumbnail", "")
            condition = item.get("condition", "new")
            available = item.get("available_quantity", 0) > 0

            if not item_id or price is None:
                continue

            results.append(
                ProductData(
                    name=name,
                    price=float(price),
                    url=url,
                    store=self.store_name,
                    external_id=item_id,
                    available=available,
                    category=query,
                    image_url=thumbnail,
                    extra={"condition": condition},
                )
            )

        logger.info(
            "[mercadolibre] Found %d products for '%s'", len(results), query
        )
        return results
