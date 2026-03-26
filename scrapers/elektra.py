"""
Elektra Mexico scraper.

Elektra uses the VTEX Commerce Platform.

Primary strategy — VTEX catalog REST API (returns JSON, no JS required):
  GET https://www.elektra.mx/api/catalog_system/pub/products/search
      ?ft=<query>&_from=0&_to=49&O=OrderByScoreDESC

The API is public and does not require authentication.

Fallback strategy — HTML search page:
  https://www.elektra.mx/<query>?_q=<query>&map=ft
  (VTEX full-text search URL pattern)
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.elektra.mx"
_CATALOG_API = f"{_BASE_URL}/api/catalog_system/pub/products/search"
_SEARCH_URL = f"{_BASE_URL}/busqueda"   # HTML fallback

# Page size for the VTEX API request
_PAGE_SIZE = 50

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


class ElektraScraper(BaseScraper):
    """Scraper for Elektra Mexico (elektra.mx).

    Uses the VTEX catalog REST API as the primary data source, falling back
    to HTML search-page scraping when the API is unavailable.

    Search URL example (VTEX full-text):
      https://www.elektra.mx/iphones?_q=iphones&map=ft
    Catalog API example:
      https://www.elektra.mx/api/catalog_system/pub/products/search?ft=iphones&_from=0&_to=49
    """

    store_name = "elektra"
    BASE_URL = _BASE_URL

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
                logger.error("[elektra] Error scraping '%s': %s", query, exc)
        return products

    # ── private ───────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[ProductData]:
        """Try VTEX catalog API first, fall back to HTML scraping."""
        results = self._search_api(query)
        if results:
            return results
        logger.info(
            "[elektra] API returned 0 products for '%s' — trying HTML fallback", query
        )
        return self._search_html(query)

    def _search_api(self, query: str) -> list[ProductData]:
        """Fetch products via the VTEX catalog REST API (returns JSON)."""
        params = {
            "ft": query,
            "_from": 0,
            "_to": _PAGE_SIZE - 1,
            "O": "OrderByScoreDESC",
        }
        try:
            resp = self.get(_CATALOG_API, params=params)
            data: list[dict] = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[elektra] Catalog API error for '%s': %s", query, exc)
            return []

        if not isinstance(data, list):
            logger.warning("[elektra] Unexpected API response type for '%s'", query)
            return []

        results: list[ProductData] = []
        for item in data:
            product_id = str(item.get("productId") or item.get("productReference") or "")
            name = item.get("productName") or item.get("productTitle") or ""
            link = item.get("link") or item.get("url") or ""
            if not product_id or not name:
                continue

            # Price lives inside items[0].sellers[0].commertialOffer.Price
            price: float | None = None
            image_url: str | None = None
            available = False
            items = item.get("items") or []
            if items:
                first_item = items[0]
                sellers = first_item.get("sellers") or []
                if sellers:
                    offer = sellers[0].get("commertialOffer") or {}
                    price_raw = offer.get("Price") or offer.get("ListPrice")
                    if price_raw is not None:
                        try:
                            price = float(price_raw)
                        except (TypeError, ValueError):
                            price = None
                    avail_qty = offer.get("AvailableQuantity", 0)
                    available = avail_qty > 0

                images = first_item.get("images") or []
                if images:
                    image_url = images[0].get("imageUrl")

            if price is None or price <= 0:
                continue

            # Ensure absolute URL
            if link and not link.startswith("http"):
                link = _BASE_URL + link

            categories = item.get("categories") or []
            category = _parse_category(categories) or query

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=link or _SEARCH_URL,
                    store=self.store_name,
                    external_id=product_id,
                    available=available,
                    category=category,
                    image_url=image_url,
                )
            )

        logger.info("[elektra] API found %d products for '%s'", len(results), query)
        return results

    def _search_html(self, query: str) -> list[ProductData]:
        """Scrape the VTEX search HTML page as a fallback."""
        # VTEX full-text search: /<query>?_q=<query>&map=ft
        url = f"{_BASE_URL}/{query.replace(' ', '-')}"
        params = {"_q": query, "map": "ft"}
        try:
            soup = self.soup(url, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []
        # VTEX search pages use various card class patterns
        cards = soup.select(
            "div[class*='product-summary'], "
            "article[class*='product'], "
            "div[class*='vtex-product-summary'], "
            "div[class*='productCard']"
        )

        for idx, card in enumerate(cards):
            name_tag = card.select_one(
                "span[class*='product-summary-name'], "
                "span[class*='productName'], "
                "h2, h3"
            )
            price_tag = card.select_one(
                "span[class*='product-summary-selling-price'], "
                "span[class*='sellingPrice'], "
                "span[class*='price'], "
                "span[class*='Price']"
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
                _BASE_URL + href if href.startswith("/") else href
            ) or url

            img_tag = card.select_one("img")
            image_url = (img_tag.get("src") or img_tag.get("data-src")) if img_tag else None

            product_id = (
                card.get("data-product-id")
                or card.get("data-id")
                or card.get("data-sku")
                or f"elektra_{query}_{idx}"
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

        logger.info("[elektra] HTML found %d products for '%s'", len(results), query)
        return results


def _parse_category(categories: list) -> str | None:
    """Extract the deepest category name from a VTEX categories list.

    VTEX returns categories as a list of path strings, e.g.
    ``["/Electrónica/Celulares/", "/Electrónica/"]``.  We take the first
    entry and extract the last non-empty path segment.
    """
    if not categories:
        return None
    path: str = categories[0] if isinstance(categories[0], str) else ""
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else None
