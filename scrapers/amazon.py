"""
Amazon Mexico scraper.

Scrapes the Amazon Mexico search results page to find products.

Anti-bot notes
--------------
Amazon aggressively blocks datacenter IPs (Railway/cloud). Strategies used
to improve hit rate:

* Realistic browser-like request headers (Accept, Accept-Encoding, etc.)
* Randomised User-Agent selection from a pool of common browser strings.
* Exponential back-off on 503/429 (inherited from BaseScraper.get).

For higher volume / more reliable access, consider using the Product
Advertising API v5 (set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, and
AMAZON_PARTNER_TAG environment variables).
"""
from __future__ import annotations

import logging
import random
import re

import requests

from scrapers.base import BaseScraper, ProductData

logger = logging.getLogger(__name__)

# ── User-Agent pool ────────────────────────────────────────────────────────────
# Rotate across recent desktop browser strings to reduce bot-detection rate.
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
]

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
    "iphone",
    "smartwatch",
]

# ── Selector sets (tried in order) ────────────────────────────────────────────
# Amazon changes its HTML structure periodically; we try several known patterns.

_NAME_SELECTORS = [
    "h2 a span",
    "h2 span.a-size-medium",
    "h2 span.a-size-base-plus",
    "h2 span.a-color-base",
    "span[data-hook='title']",
    "span.rush-component span",
]

_CARD_SELECTORS = [
    "div[data-asin][data-component-type='s-search-result']",
    "div[data-asin][data-index]",
    "div[data-asin].s-result-item",
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
        # Override the base-class headers with more realistic browser headers
        self.session.headers.update(self._browser_headers())

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

    @staticmethod
    def _browser_headers() -> dict:
        """Return a set of headers that mimic a real desktop browser."""
        ua = random.choice(_USER_AGENTS)
        return {
            "User-Agent": ua,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    def _scrape_search(self, query: str) -> list[ProductData]:
        """Scrape one search-results page for *query* and return products."""
        # Rotate User-Agent on each request to reduce fingerprinting
        self.session.headers.update(self._browser_headers())

        params = {"k": query, "i": "aps", "ref": "sr_pg_1"}
        try:
            soup = self.soup(self.SEARCH_URL, params=params)
        except requests.RequestException as exc:
            logger.warning("[amazon] Request failed for '%s': %s", query, exc)
            return []

        # Find product cards — try each selector set until we get cards
        cards = []
        for selector in _CARD_SELECTORS:
            cards = soup.select(selector)
            if cards:
                logger.debug(
                    "[amazon] '%s' — found %d cards with selector %r",
                    query,
                    len(cards),
                    selector,
                )
                break

        if not cards:
            # Log a snippet of the response to help diagnose bot-blocks / layout changes
            logger.warning(
                "[amazon] No product cards found for '%s'. "
                "Page title: %r. "
                "This may indicate bot-detection (503/CAPTCHA) or a layout change.",
                query,
                soup.title.string if soup.title else "N/A",
            )
            return []

        results: list[ProductData] = []
        for card in cards:
            asin = card.get("data-asin", "").strip()
            if not asin:
                continue

            # --- Product name: try selectors in order -------------------------
            name = ""
            for sel in _NAME_SELECTORS:
                tag = card.select_one(sel)
                if tag:
                    candidate = tag.get_text(strip=True)
                    # Skip very short strings that are likely icons/aria labels
                    if len(candidate) > 5:
                        name = candidate
                        break
            if not name:
                continue

            # --- Price -------------------------------------------------------
            price = self._extract_price(card)
            if price is None:
                continue

            # --- URL ---------------------------------------------------------
            link_tag = card.select_one("h2 a") or card.select_one("a.a-link-normal[href*='/dp/']")
            relative_url = link_tag["href"] if link_tag else f"/dp/{asin}"
            url = self.BASE_URL + relative_url.split("?")[0]

            # --- Image -------------------------------------------------------
            img_tag = card.select_one("img.s-image") or card.select_one("img[data-image-index]")
            image_url = img_tag["src"] if img_tag else None

            results.append(
                ProductData(
                    name=name,
                    price=price,
                    url=url,
                    store=self.store_name,
                    external_id=asin,
                    available=True,
                    category=query,
                    image_url=image_url,
                )
            )

        logger.info("[amazon] Found %d products for '%s'", len(results), query)
        return results

    @staticmethod
    def _extract_price(card) -> float | None:
        """Extract a price from a search result card.

        Tries, in order:
        1. ``span.a-offscreen`` — contains the full human-readable price string
           (e.g. "$12,999.00") that Amazon renders for screen-readers.
        2. ``span.a-price-whole`` + ``span.a-price-fraction``.
        3. Any element whose text matches a price pattern (last resort).
        """
        # Strategy 1: a-offscreen (most reliable, full price string)
        offscreen = card.select_one("span.a-offscreen")
        if offscreen:
            price = BaseScraper.clean_price(offscreen.get_text(strip=True))
            if price is not None and price > 0:
                return price

        # Strategy 2: whole + fraction spans
        whole = card.select_one("span.a-price-whole")
        if whole:
            price_str = whole.get_text(strip=True).rstrip(".")
            fraction = card.select_one("span.a-price-fraction")
            if fraction:
                price_str += "." + fraction.get_text(strip=True)
            price = BaseScraper.clean_price(price_str)
            if price is not None and price > 0:
                return price

        # Strategy 3: regex scan for a price pattern in the card text
        card_text = card.get_text(" ", strip=True)
        match = re.search(r"\$\s*([\d,]+(?:\.\d{1,2})?)", card_text)
        if match:
            price = BaseScraper.clean_price(match.group(0))
            if price is not None and price > 0:
                return price

        return None

