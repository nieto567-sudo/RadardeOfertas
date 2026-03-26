"""
Falabella Mexico scraper.

Falabella (falabella.com.mx) is a major department store chain in Mexico
offering electronics, appliances, clothing, and more.

The site is built on the Falabella Commerce Platform which exposes a public
REST API returning JSON results.

Primary strategy — Falabella MX product-listing REST API:
  GET https://www.falabella.com.mx/s/browse/v2/listing/mx
      ?Ntt=<query>&pgid=<category_pgid>&currentPage=0&resultsPerPage=48

Fallback strategy — HTML search page:
  https://www.falabella.com.mx/falabella-mx/search?Ntt=<query>
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.falabella.com.mx"
_API_LISTING = f"{_BASE_URL}/s/browse/v2/listing/mx"
_HTML_SEARCH = f"{_BASE_URL}/falabella-mx/search"
_PAGE_SIZE = 48

# Main category pgids used in the Falabella MX API
# Format: (query_label, Ntt_term, pgid)  — pgid can be empty for free-text search
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
    "samsung galaxy",
]


class FalabellaScraper(BaseScraper):
    """Scraper for Falabella Mexico (falabella.com.mx).

    Uses the Falabella listing REST API as the primary data source, with
    an HTML fallback.

    API example:
      https://www.falabella.com.mx/s/browse/v2/listing/mx?Ntt=laptop&currentPage=0&resultsPerPage=48
    HTML example:
      https://www.falabella.com.mx/falabella-mx/search?Ntt=laptop
    """

    store_name = "falabella"
    BASE_URL = _BASE_URL

    def __init__(self) -> None:
        super().__init__()
        self.queries = DEFAULT_QUERIES
        # Falabella API expects JSON response
        self.session.headers.update(
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    # ── public ────────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[falabella] Error scraping '%s': %s", query, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[ProductData]:
        """Try JSON API first, fall back to HTML."""
        results = self._search_api(query)
        if results:
            return results
        logger.info(
            "[falabella] API returned 0 for '%s' — trying HTML fallback", query
        )
        return self._search_html(query)

    def _search_api(self, query: str) -> list[ProductData]:
        """Fetch products via Falabella listing REST API."""
        params = {
            "Ntt": query,
            "currentPage": 0,
            "resultsPerPage": _PAGE_SIZE,
            "sortBy": "BEST_MATCH",
        }
        try:
            resp = self.get(_API_LISTING, params=params)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[falabella] API error for '%s': %s", query, exc)
            return []

        # The API response structure:
        # data["data"]["results"] is a list of product dicts
        # OR data["results"] at top level
        if not isinstance(data, dict):
            logger.warning("[falabella] Unexpected API response for '%s'", query)
            return []

        records: list = (
            (data.get("data") or {}).get("results")
            or data.get("results")
            or data.get("records")
            or []
        )

        results: list[ProductData] = []
        for item in records:
            if not isinstance(item, dict):
                continue

            product_id = str(
                item.get("productId")
                or item.get("id")
                or item.get("skuId")
                or ""
            )
            name = (
                item.get("displayName")
                or item.get("name")
                or item.get("title")
                or ""
            )
            if not product_id or not name:
                continue

            # Price: prefer offer price (salePrice) over list price
            prices = item.get("prices") or {}
            price_raw = (
                prices.get("salePrice")
                or prices.get("normalPrice")
                or prices.get("originalPrice")
                or item.get("price")
                or item.get("salePrice")
                or item.get("normalPrice")
            )
            if price_raw is None:
                continue
            price = self.clean_price(str(price_raw))
            if price is None or price <= 0:
                continue

            # URL
            url_path = (
                item.get("url")
                or item.get("pdpUrl")
                or item.get("productUrl")
                or ""
            )
            product_url = (
                _BASE_URL + url_path if url_path.startswith("/") else url_path
            ) or _HTML_SEARCH

            # Image
            media = item.get("media") or []
            image_url: str | None = None
            if media and isinstance(media, list):
                first = media[0] if media else {}
                image_url = first.get("url") or first.get("src") or None
            if not image_url:
                image_url = item.get("imageUrl") or item.get("thumbnailUrl") or None

            # Category
            breadcrumbs = item.get("breadcrumb") or []
            category = (
                breadcrumbs[-1].get("displayName") if breadcrumbs else None
            ) or query

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=product_url,
                    store=self.store_name,
                    external_id=product_id,
                    available=True,
                    category=category,
                    image_url=image_url,
                )
            )

        logger.info("[falabella] API found %d products for '%s'", len(results), query)
        return results

    def _search_html(self, query: str) -> list[ProductData]:
        """Scrape the Falabella MX HTML search results page."""
        params = {"Ntt": query}
        try:
            soup = self.soup(_HTML_SEARCH, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []
        # Falabella uses product pods with various class patterns
        cards = soup.select(
            "div[class*='pod-plp'], "
            "div[class*='product-item'], "
            "li[class*='product'], "
            "article[class*='product']"
        )

        for idx, card in enumerate(cards):
            name_tag = card.select_one(
                "b[class*='pod-subTitle'], "
                "span[class*='product-name'], "
                "h2, h3"
            )
            price_tag = card.select_one(
                "li[class*='prices-0'] span, "
                "span[class*='price'], "
                "div[class*='price'] span"
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

            product_id = (
                card.get("data-product-id")
                or card.get("data-id")
                or f"falabella_{query}_{idx}"
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

        logger.info("[falabella] HTML found %d products for '%s'", len(results), query)
        return results
