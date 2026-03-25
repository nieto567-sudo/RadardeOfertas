"""
Base scraper class that all store scrapers inherit from.

Each concrete scraper must implement:
    * scrape() -> list[ProductData]

A ProductData is a plain dict with the keys documented below.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

# Retry configuration (env-configurable via config/settings.py)
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0   # seconds
_JITTER_MAX = 1.0     # seconds of random jitter added to each wait


@dataclass
class ProductData:
    """Normalised data returned by every scraper."""

    name: str
    price: float
    url: str
    store: str
    external_id: str
    available: bool = True
    category: Optional[str] = None
    image_url: Optional[str] = None
    # Coupon code found on the product page (if any)
    coupon_code: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "price": self.price,
            "url": self.url,
            "store": self.store,
            "external_id": self.external_id,
            "available": self.available,
            "category": self.category,
            "image_url": self.image_url,
            "coupon_code": self.coupon_code,
        }


class BaseScraper:
    """
    Provides a shared HTTP session with sensible defaults.

    Sub-classes implement :meth:`scrape` which returns a list of
    :class:`ProductData` instances.
    """

    store_name: str = "unknown"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.USER_AGENT,
                "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self.timeout = settings.REQUEST_TIMEOUT
        self.delay = settings.REQUEST_DELAY_SECONDS

    # ── helpers ───────────────────────────────────────────────────────────────

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Perform a GET request with the shared session, a polite delay, and
        automatic retry with exponential backoff + jitter on transient errors.

        Non-transient HTTP errors (400, 401, 403, 404) are raised immediately
        without retrying — they indicate a permanent client-side issue (e.g.
        wrong URL or forbidden resource) that will not resolve on its own.

        Transient errors (429, 500, 502, 503, 504) and network/connection
        errors are retried up to ``_MAX_RETRIES`` times.
        """
        # HTTP status codes that should NOT be retried (permanent client errors)
        _NO_RETRY_STATUSES = frozenset({400, 401, 403, 404})

        time.sleep(self.delay)
        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as exc:
                # Do not retry permanent client-side errors
                if exc.response is not None and exc.response.status_code in _NO_RETRY_STATUSES:
                    logger.warning(
                        "[%s] GET %s returned %d — not retrying",
                        self.store_name,
                        url,
                        exc.response.status_code,
                    )
                    raise
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** attempt + random.uniform(0, _JITTER_MAX)
                    logger.warning(
                        "[%s] GET %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        self.store_name,
                        url,
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "[%s] GET %s failed after %d attempts: %s",
                        self.store_name,
                        url,
                        _MAX_RETRIES,
                        exc,
                    )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** attempt + random.uniform(0, _JITTER_MAX)
                    logger.warning(
                        "[%s] GET %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        self.store_name,
                        url,
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "[%s] GET %s failed after %d attempts: %s",
                        self.store_name,
                        url,
                        _MAX_RETRIES,
                        exc,
                    )
        raise last_exc  # type: ignore[misc]

    def soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Return a BeautifulSoup tree for a URL."""
        resp = self.get(url, **kwargs)
        return BeautifulSoup(resp.text, "lxml")

    @staticmethod
    def clean_price(raw: str) -> Optional[float]:
        """
        Convert a price string like '$1,299.00' or '1299' to a float.
        Returns None when parsing is not possible.
        """
        if not raw:
            return None
        cleaned = raw.strip().replace("$", "").replace(",", "").replace(" ", "")
        # Remove currency codes (MXN, USD, etc.)
        for code in ("MXN", "USD", "mxn", "usd"):
            cleaned = cleaned.replace(code, "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    # ── interface ─────────────────────────────────────────────────────────────

    def scrape(self) -> list[ProductData]:  # pragma: no cover
        """
        Scrape products from the store.

        Must be overridden by each sub-class.
        Returns a list of :class:`ProductData` objects.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement scrape()"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} store={self.store_name!r}>"
