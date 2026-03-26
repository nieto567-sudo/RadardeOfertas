"""
Best Buy Mexico scraper.

Best Buy Mexico (bestbuy.com.mx) is one of the largest electronics retailers
in Mexico.  The site is powered by a REST API that returns JSON, making it
far more reliable than HTML scraping.

Primary strategy — Best Buy MX search REST API:
  GET https://www.bestbuy.com.mx/api/2.0/page/components/search
      ?term=<query>&start=0&count=48&facetsUrl=...

Fallback strategy — HTML search page:
  https://www.bestbuy.com.mx/busqueda?q=<query>
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.bestbuy.com.mx"
_API_SEARCH = f"{_BASE_URL}/api/2.0/page/components/search"
_HTML_SEARCH = f"{_BASE_URL}/busqueda"
_PAGE_SIZE = 48

DEFAULT_QUERIES = [
    "laptop",
    "televisión",
    "smartphone",
    "tablet",
    "consola",
    "auriculares",
    "monitor",
    "smartwatch",
    "cámara",
    "iphone",
    "samsung galaxy",
]


class BestBuyScraper(BaseScraper):
    """Scraper for Best Buy Mexico (bestbuy.com.mx).

    Uses the internal JSON search API as primary data source, falling back
    to HTML scraping when the API is unavailable.

    Search URL example (HTML):
      https://www.bestbuy.com.mx/busqueda?q=laptop
    API example:
      https://www.bestbuy.com.mx/api/2.0/page/components/search?term=laptop&start=0&count=48
    """

    store_name = "bestbuy"
    BASE_URL = _BASE_URL

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES
        # Best Buy MX API requires these headers to return JSON
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "x-client-name": "web",
            }
        )

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[bestbuy] Error scraping '%s': %s", query, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[ProductData]:
        """Try JSON API first, fall back to HTML."""
        results = self._search_api(query)
        if results:
            return results
        logger.info(
            "[bestbuy] API returned 0 for '%s' — trying HTML fallback", query
        )
        return self._search_html(query)

    def _search_api(self, query: str) -> list[ProductData]:
        """Fetch products via Best Buy MX JSON search API."""
        params = {
            "term": query,
            "start": 0,
            "count": _PAGE_SIZE,
        }
        try:
            resp = self.get(_API_SEARCH, params=params)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[bestbuy] API error for '%s': %s", query, exc)
            return []

        # Navigate response tree: could be different layouts
        # Common: data["components"][0]["record"]["products"] or data["products"]
        products_raw: list = []
        if isinstance(data, dict):
            # Try known response structures
            components = data.get("components") or []
            for comp in components:
                if isinstance(comp, dict):
                    rec = comp.get("record") or {}
                    prods = rec.get("products") or comp.get("products") or []
                    if prods:
                        products_raw = prods
                        break
            if not products_raw:
                products_raw = data.get("products") or data.get("results") or []
        elif isinstance(data, list):
            products_raw = data

        results: list[ProductData] = []
        for item in products_raw:
            if not isinstance(item, dict):
                continue

            sku = str(item.get("sku") or item.get("id") or item.get("productId") or "")
            name = item.get("name") or item.get("title") or item.get("displayName") or ""
            if not sku or not name:
                continue

            # Price: salePrice > regularPrice
            price_raw = (
                item.get("salePrice")
                or item.get("currentPrice")
                or item.get("regularPrice")
                or item.get("price")
            )
            if price_raw is None:
                continue
            price = self.clean_price(str(price_raw))
            if price is None or price <= 0:
                continue

            # URL
            url_path = item.get("url") or item.get("pdpUrl") or f"/p/{sku}"
            product_url = (
                _BASE_URL + url_path if url_path.startswith("/") else url_path
            )

            # Image
            image_raw = (
                item.get("image")
                or item.get("thumbnailImage")
                or item.get("imageUrl")
                or ""
            )
            image_url = (
                _BASE_URL + image_raw if image_raw.startswith("/") else image_raw
            ) or None

            # Availability
            available = bool(
                item.get("onSale")
                or item.get("inStoreAvailability")
                or item.get("availableForShipping")
                or item.get("available", True)
            )

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=product_url,
                    store=self.store_name,
                    external_id=sku,
                    available=available,
                    category=query,
                    image_url=image_url or None,
                )
            )

        logger.info("[bestbuy] API found %d products for '%s'", len(results), query)
        return results

    def _search_html(self, query: str) -> list[ProductData]:
        """Scrape the Best Buy MX HTML search results page."""
        params = {"q": query}
        try:
            soup = self.soup(_HTML_SEARCH, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []
        # Best Buy uses several class patterns; try the most common ones
        cards = soup.select(
            "li[class*='sku-item'], "
            "div[class*='product-item'], "
            "article[class*='product'], "
            "div[class*='ProductCard']"
        )

        for idx, card in enumerate(cards):
            name_tag = card.select_one(
                "h4[class*='sku-title'] a, "
                "h2[class*='product-title'], "
                "span[class*='product-name'], "
                "a[class*='product-title']"
            )
            price_tag = card.select_one(
                "div[class*='priceView-hero-price'] span, "
                "span[class*='sr-only'], "
                "span[class*='price-display'], "
                "span[class*='price']"
            )
            if not name_tag or not price_tag:
                continue

            name = name_tag.get_text(strip=True)
            price = self.clean_price(price_tag.get_text(strip=True))
            if not name or price is None or price <= 0:
                continue

            link_tag = card.select_one("a[href]")
            href = link_tag["href"] if link_tag else ""
            product_url = (
                _BASE_URL + href if href.startswith("/") else href
            ) or _HTML_SEARCH

            img_tag = card.select_one("img")
            image_url = (img_tag.get("src") or img_tag.get("data-src")) if img_tag else None

            sku = (
                card.get("data-sku-id")
                or card.get("data-id")
                or f"bestbuy_{query}_{idx}"
            )

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=product_url,
                    store=self.store_name,
                    external_id=str(sku),
                    available=True,
                    category=query,
                    image_url=image_url,
                )
            )

        logger.info("[bestbuy] HTML found %d products for '%s'", len(results), query)
        return results
