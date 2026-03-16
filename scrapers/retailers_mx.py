"""
Additional Mexican retailer scrapers: Costco, Coppel, Elektra, Sears,
Sanborns, Sam's Club, Office Depot / OfficeMax, Soriana.

Each follows the same lightweight pattern: scrape search-results HTML,
extract product cards, return a list of ProductData.
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

# ── Shared search terms ───────────────────────────────────────────────────────
_DEFAULT_QUERIES = [
    "laptop",
    "televisión",
    "smartphone",
    "tablet",
    "cafetera",
]


# ── Helper mixin ──────────────────────────────────────────────────────────────

class _SimpleSearchScraper(BaseScraper):
    """
    Shared logic for scraping simple search pages.

    Sub-classes must set:
        * store_name
        * SEARCH_URL
        * BASE_URL
        * _css_card   – CSS selector to find product cards
        * _css_name   – CSS selector for product name within a card
        * _css_price  – CSS selector for price within a card
        * _css_link   – CSS selector for link within a card
        * _css_img    – CSS selector for image within a card
        * _q_param    – query-string param name for the search term
    """

    BASE_URL: str = ""
    SEARCH_URL: str = ""
    _css_card: str = ""
    _css_name: str = ""
    _css_price: str = ""
    _css_link: str = "a[href]"
    _css_img: str = "img"
    _q_param: str = "q"

    def __init__(self) -> None:
        super().__init__()
        self.queries = _DEFAULT_QUERIES

    def scrape(self) -> list[ProductData]:
        products: list[ProductData] = []
        for query in self.queries:
            try:
                products.extend(self._scrape_search(query))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("[%s] Error scraping '%s': %s", self.store_name, query, exc)
        return products

    def _scrape_search(self, query: str) -> list[ProductData]:
        params = {self._q_param: query}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException:
            return []

        results: list[ProductData] = []
        for idx, card in enumerate(soup.select(self._css_card)):
            name_tag = card.select_one(self._css_name)
            price_tag = card.select_one(self._css_price)
            if not name_tag or not price_tag:
                continue

            name = name_tag.get_text(strip=True)
            price = self.clean_price(price_tag.get_text(strip=True))
            if not name or price is None:
                continue

            link_tag = card.select_one(self._css_link)
            href = link_tag["href"] if link_tag else ""
            url = (
                self.BASE_URL + href if href.startswith("/") else href
            ) or self.SEARCH_URL

            img_tag = card.select_one(self._css_img)
            image_url = (
                img_tag.get("src") or img_tag.get("data-src") if img_tag else None
            )

            product_id = (
                card.get("data-id")
                or card.get("data-sku")
                or card.get("data-product-id")
                or f"{self.store_name}_{query}_{idx}"
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

        logger.info("[%s] Found %d products for '%s'", self.store_name, len(results), query)
        return results


# ── Concrete scrapers ─────────────────────────────────────────────────────────


class CostcoScraper(_SimpleSearchScraper):
    store_name = "costco"
    BASE_URL = "https://www.costco.com.mx"
    SEARCH_URL = "https://www.costco.com.mx/search"
    _css_card = "div[class*='product'], article[class*='product']"
    _css_name = "span[class*='description'], h3, [class*='product-title']"
    _css_price = "span[class*='price'], [class*='Price']"
    _q_param = "q"


class CoppelScraper(_SimpleSearchScraper):
    store_name = "coppel"
    BASE_URL = "https://www.coppel.com"
    SEARCH_URL = "https://www.coppel.com/search"
    _css_card = "div[class*='product-item'], li[class*='product']"
    _css_name = "p[class*='name'], span[class*='name'], h3"
    _css_price = "p[class*='price'], span[class*='price']"
    _q_param = "q"


class ElektraScraper(_SimpleSearchScraper):
    store_name = "elektra"
    BASE_URL = "https://www.elektra.com.mx"
    SEARCH_URL = "https://www.elektra.com.mx/busqueda"
    _css_card = "div[class*='product-card'], div[class*='product-item']"
    _css_name = "h3, span[class*='title'], p[class*='name']"
    _css_price = "span[class*='price'], p[class*='price']"
    _q_param = "q"


class SearsScraper(_SimpleSearchScraper):
    store_name = "sears"
    BASE_URL = "https://www.sears.com.mx"
    SEARCH_URL = "https://www.sears.com.mx/search"
    _css_card = "div[class*='product-tile'], div[class*='product-card']"
    _css_name = "span[class*='name'], h3"
    _css_price = "span[class*='price']"
    _q_param = "q"


class SanbornsScraper(_SimpleSearchScraper):
    store_name = "sanborns"
    BASE_URL = "https://www.sanborns.com.mx"
    SEARCH_URL = "https://www.sanborns.com.mx/search"
    _css_card = "div[class*='product-tile'], div[class*='product-card']"
    _css_name = "span[class*='name'], h3"
    _css_price = "span[class*='price']"
    _q_param = "q"


class SamsClubScraper(_SimpleSearchScraper):
    store_name = "sams_club"
    BASE_URL = "https://www.sams.com.mx"
    SEARCH_URL = "https://www.sams.com.mx/search"
    _css_card = "div[class*='product'], article[class*='product']"
    _css_name = "p[class*='name'], span[class*='title'], h3"
    _css_price = "span[class*='price'], p[class*='price']"
    _q_param = "q"


class OfficeDepotScraper(_SimpleSearchScraper):
    store_name = "office_depot"
    BASE_URL = "https://www.officedepot.com.mx"
    SEARCH_URL = "https://www.officedepot.com.mx/buscar"
    _css_card = "div[class*='product-item'], li[class*='item']"
    _css_name = "strong[class*='product-item-name'], span[class*='name']"
    _css_price = "span[class*='price'], [data-price-type]"
    _q_param = "q"


class OfficeMaxScraper(_SimpleSearchScraper):
    store_name = "officemax"
    BASE_URL = "https://www.officemax.com.mx"
    SEARCH_URL = "https://www.officemax.com.mx/buscar"
    _css_card = "div[class*='product-item'], li[class*='item']"
    _css_name = "strong[class*='product-item-name'], span[class*='name']"
    _css_price = "span[class*='price'], [data-price-type]"
    _q_param = "q"


class SorianaScraper(_SimpleSearchScraper):
    store_name = "soriana"
    BASE_URL = "https://www.soriana.com"
    SEARCH_URL = "https://www.soriana.com/search"
    _css_card = "div[class*='product-tile'], div[class*='product-card']"
    _css_name = "div[class*='tile-body'] span, h3"
    _css_price = "span[class*='price']"
    _q_param = "q"
