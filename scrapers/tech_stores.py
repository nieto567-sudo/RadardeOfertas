"""
Technology store scrapers for Mexico:
Cyberpuerta, DDTech, PCEL, Intercompras, Gameplanet, Claro Shop.
"""
from __future__ import annotations

import logging

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

_TECH_QUERIES = [
    "laptop",
    "smartphone",
    "monitor",
    "procesador",
    "tarjeta gráfica",
    "ssd",
    "consola",
    "audífonos",
]


class _TechSearchScraper(BaseScraper):
    """Shared logic for Mexican tech retailers."""

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
        self.queries = _TECH_QUERIES

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
                card.get("data-id")
                or card.get("data-sku")
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


class CyberpuertaScraper(_TechSearchScraper):
    store_name = "cyberpuerta"
    BASE_URL = "https://www.cyberpuerta.mx"
    SEARCH_URL = "https://www.cyberpuerta.mx/Buscar/"
    _css_card = "div[class*='cp-product'], li[class*='article']"
    _css_name = "span[class*='productTitle'], h2"
    _css_price = "span[class*='price'], p[class*='price']"
    _q_param = "q"


class DDTechScraper(_TechSearchScraper):
    store_name = "ddtech"
    BASE_URL = "https://www.ddtech.com.mx"
    SEARCH_URL = "https://www.ddtech.com.mx/search"
    _css_card = "div[class*='product-item'], li[class*='product']"
    _css_name = "h2[class*='product-name'], span[class*='name']"
    _css_price = "span[class*='price']"
    _q_param = "q"


class PCELScraper(_TechSearchScraper):
    store_name = "pcel"
    BASE_URL = "https://www.pcel.com"
    SEARCH_URL = "https://www.pcel.com/busqueda"
    _css_card = "div[class*='product'], li[class*='product']"
    _css_name = "h3, span[class*='nombre']"
    _css_price = "span[class*='precio'], span[class*='price']"
    _q_param = "q"


class IntercomprasScraper(_TechSearchScraper):
    store_name = "intercompras"
    BASE_URL = "https://www.intercompras.com"
    SEARCH_URL = "https://www.intercompras.com/buscar"
    _css_card = "div[class*='product-item'], div[class*='product-card']"
    _css_name = "p[class*='name'], span[class*='title']"
    _css_price = "span[class*='price']"
    _q_param = "q"


class GameplanetScraper(_TechSearchScraper):
    store_name = "gameplanet"
    BASE_URL = "https://www.gameplanet.com.mx"
    SEARCH_URL = "https://www.gameplanet.com.mx/busqueda"
    _css_card = "div[class*='product-item'], div[class*='item-product']"
    _css_name = "h2, span[class*='product-name']"
    _css_price = "span[class*='price'], p[class*='price']"
    _q_param = "q"


class ClaroShopScraper(_TechSearchScraper):
    store_name = "claro_shop"
    BASE_URL = "https://www.claroshop.com"
    SEARCH_URL = "https://www.claroshop.com/busqueda"
    _css_card = "div[class*='product-item'], article[class*='product']"
    _css_name = "span[class*='product-title'], h3"
    _css_price = "span[class*='price']"
    _q_param = "q"
