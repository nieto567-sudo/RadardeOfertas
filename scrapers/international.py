"""
International store scrapers: AliExpress, eBay, Newegg, Banggood, Gearbest.
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_INTL_QUERIES = [
    "laptop",
    "smartphone",
    "earbuds",
    "smartwatch",
    "drone",
]


class _IntlSearchScraper(BaseScraper):
    """Shared logic for international stores."""

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
        self.queries = _INTL_QUERIES

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
            url = (self.BASE_URL + href if href.startswith("/") else href) or self.SEARCH_URL

            img_tag = card.select_one(self._css_img)
            image_url = (img_tag.get("src") or img_tag.get("data-src")) if img_tag else None

            product_id = (
                card.get("data-item-id")
                or card.get("data-id")
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


class AliExpressScraper(_IntlSearchScraper):
    store_name = "aliexpress"
    BASE_URL = "https://www.aliexpress.com"
    SEARCH_URL = "https://www.aliexpress.com/wholesale"
    _css_card = "a[class*='manhattan--titleText'], div[class*='product-snippet']"
    _css_name = "h1[class*='title'], span[class*='title']"
    _css_price = "div[class*='price'], span[class*='price--current']"
    _q_param = "SearchText"


class eBayScraper(_IntlSearchScraper):
    store_name = "ebay"
    BASE_URL = "https://www.ebay.com"
    SEARCH_URL = "https://www.ebay.com/sch/i.html"
    _css_card = "li[class*='s-item']"
    _css_name = "div[class*='s-item__title'] span, h3[class*='s-item__title']"
    _css_price = "span[class*='s-item__price']"
    _q_param = "_nkw"


class NeweggScraper(_IntlSearchScraper):
    store_name = "newegg"
    BASE_URL = "https://www.newegg.com"
    SEARCH_URL = "https://www.newegg.com/p/pl"
    _css_card = "div[class*='item-cell']"
    _css_name = "a[class*='item-title']"
    _css_price = "li[class*='price-current']"
    _q_param = "d"


class BanggoodScraper(_IntlSearchScraper):
    store_name = "banggood"
    BASE_URL = "https://www.banggood.com"
    SEARCH_URL = "https://www.banggood.com/search/products"
    _css_card = "div[class*='product-item'], div[id*='js-product-']"
    _css_name = "a[class*='product-title'], p[class*='title']"
    _css_price = "span[class*='main-price'], p[class*='price']"
    _q_param = "keywords"


class GearbestScraper(_IntlSearchScraper):
    """Gearbest – note: site may have limited availability; kept for completeness."""

    store_name = "gearbest"
    BASE_URL = "https://www.gearbest.com"
    SEARCH_URL = "https://www.gearbest.com/promotions/search_result.html"
    _css_card = "div[class*='item'], li[class*='product-item']"
    _css_name = "p[class*='title'], span[class*='name']"
    _css_price = "span[class*='price']"
    _q_param = "q"
