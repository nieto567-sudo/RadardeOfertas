"""
Coppel Mexico scraper.

Coppel's website is a React SPA backed by an internal API. Two complementary
strategies are used:

1. **Search API** (primary) — Coppel exposes a JSON endpoint for text search:
     GET https://www.coppel.com/api/search?Ntt=<query>&Nr=product.siteId:MX
   Returns a JSON object with product listings.

2. **HTML search page** (fallback) — traditional HTML scraping of:
     https://www.coppel.com/busqueda?Ntt=<query>

Additionally, well-known high-traffic category URLs (as provided by the
project) are scraped directly:
     https://www.coppel.com/sd/<category>?pmNodeId=<id>&prNodeId=<id>&regionTelcel=9
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.coppel.com"
_SEARCH_URL = f"{_BASE_URL}/busqueda"
_API_SEARCH_URL = f"{_BASE_URL}/api/search"

DEFAULT_QUERIES = [
    "laptop",
    "televisión",
    "smartphone",
    "tablet",
    "consola",
    "auriculares",
    "cafetera",
    "refrigerador",
    "lavadora",
    "iphone",
]

# Known category URLs that Coppel structures as /sd/<category>?pmNodeId=...
# Format: (query_label, path, pmNodeId, prNodeId)
_CATEGORY_URLS: list[tuple[str, str, str, str]] = [
    ("celulares", "celulares", "11404", "11419"),
    ("laptops", "laptops-computadoras", "10726", "10730"),
    ("televisiones", "televisiones", "11200", "11201"),
    ("tablets", "tablets", "11404", "11430"),
    ("refrigeradores", "refrigeradores", "10901", "10902"),
    ("lavadoras", "lavadoras-secadoras", "10910", "10911"),
]


class CoppelScraper(BaseScraper):
    """Scraper for Coppel Mexico (coppel.com).

    Tries the internal JSON search API first; falls back to HTML scraping of
    the standard search page, then scrapes well-known category pages.

    Category URL example (as provided):
      https://www.coppel.com/sd/celulares?pmNodeId=11404&prNodeId=11419&regionTelcel=9
    Search URL example:
      https://www.coppel.com/busqueda?Ntt=celulares
    """

    store_name = "coppel"
    BASE_URL = _BASE_URL

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        # Text-search queries
        for query in self.queries:
            try:
                products.extend(self._search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[coppel] Error scraping query '%s': %s", query, exc)
        # Known category pages
        for label, path, pm_id, pr_id in _CATEGORY_URLS:
            try:
                products.extend(self._scrape_category(label, path, pm_id, pr_id))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[coppel] Error scraping category '%s': %s", label, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[ProductData]:
        """Try JSON API first, fall back to HTML."""
        results = self._search_api(query)
        if results:
            return results
        logger.info(
            "[coppel] API returned 0 for '%s' — trying HTML fallback", query
        )
        return self._search_html(query)

    def _search_api(self, query: str) -> list[ProductData]:
        """Query Coppel's internal search JSON API."""
        params = {
            "Ntt": query,
            "Nr": "product.siteId:MX",
            "Ns": "product.sales|1",
            "Nrpp": 50,
        }
        try:
            resp = self.get(_API_SEARCH_URL, params=params)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[coppel] API error for '%s': %s", query, exc)
            return []

        # The response structure varies; try multiple known layouts.
        records = (
            data.get("products")
            or data.get("records")
            or (data.get("contents") or [{}])[0].get("records", [])
            if isinstance(data, dict)
            else []
        )

        results: list[ProductData] = []
        for rec in records:
            attrs = rec.get("attributes") or rec
            name = (
                attrs.get("product.displayName")
                or attrs.get("product.productDisplayName")
                or attrs.get("title")
                or ""
            )
            price_raw = (
                attrs.get("product.salePrice")
                or attrs.get("product.listPrice")
                or attrs.get("price")
            )
            url_path = (
                attrs.get("product.url")
                or attrs.get("url")
                or ""
            )
            product_id = (
                attrs.get("product.repositoryId")
                or attrs.get("product.id")
                or attrs.get("id")
                or ""
            )
            image_raw = attrs.get("product.thumbnailImage") or attrs.get("image") or ""

            if not name or price_raw is None:
                continue

            price = self.clean_price(str(price_raw))
            if price is None:
                continue

            full_url = (
                _BASE_URL + url_path if url_path.startswith("/") else url_path
            ) or _SEARCH_URL

            image_url = (
                _BASE_URL + image_raw if image_raw.startswith("/") else image_raw
            ) or None

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=full_url,
                    store=self.store_name,
                    external_id=str(product_id) or f"coppel_{query}_{len(results)}",
                    available=True,
                    category=query,
                    image_url=image_url or None,
                )
            )

        logger.info("[coppel] API found %d products for '%s'", len(results), query)
        return results

    def _search_html(self, query: str) -> list[ProductData]:
        """Scrape the HTML search results page."""
        params = {"Ntt": query}
        try:
            soup = self.soup(_SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        return self._parse_product_cards(soup, query)

    def _scrape_category(
        self, label: str, path: str, pm_id: str, pr_id: str
    ) -> list[ProductData]:
        """Scrape a known category page using Coppel's /sd/<category> URL format."""
        url = f"{_BASE_URL}/sd/{path}"
        params = {
            "pmNodeId": pm_id,
            "prNodeId": pr_id,
            "regionTelcel": "9",
        }
        try:
            soup = self.soup(url, params=params)
        except requests.RequestException:
            return []

        results = self._parse_product_cards(soup, label)
        logger.info(
            "[coppel] Category '%s' found %d products", label, len(results)
        )
        return results

    def _parse_product_cards(self, soup, category: str) -> list[ProductData]:
        """Extract product data from a BeautifulSoup tree (search or category page)."""
        # Coppel uses several class patterns across page types
        cards = soup.select(
            "div[class*='product-item'], "
            "li[class*='product'], "
            "article[class*='product'], "
            "div[class*='ProductCard'], "
            "div[class*='product-card']"
        )

        results: list[ProductData] = []
        for idx, card in enumerate(cards):
            name_tag = card.select_one(
                "p[class*='product-name'], "
                "p[class*='nombre'], "
                "span[class*='name'], "
                "span[class*='title'], "
                "h2, h3"
            )
            price_tag = card.select_one(
                "p[class*='price'], "
                "span[class*='price'], "
                "span[class*='precio'], "
                "[class*='Price']"
            )
            if not name_tag or not price_tag:
                continue

            name = name_tag.get_text(strip=True)
            price = self.clean_price(price_tag.get_text(strip=True))
            if not name or price is None:
                continue

            link_tag = card.select_one("a[href]")
            href = link_tag["href"] if link_tag else ""
            url = (
                _BASE_URL + href if href.startswith("/") else href
            ) or _SEARCH_URL

            img_tag = card.select_one("img")
            image_url = (img_tag.get("src") or img_tag.get("data-src")) if img_tag else None

            product_id = (
                card.get("data-id")
                or card.get("data-sku")
                or card.get("data-product-id")
                or f"coppel_{category}_{idx}"
            )

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=url,
                    store=self.store_name,
                    external_id=str(product_id),
                    available=True,
                    category=category,
                    image_url=image_url,
                )
            )

        return results
