"""
Link builder – decides between direct and monetised offer URLs.

Two operating modes are controlled by the ``MONETIZED_LINKS_ENABLED``
environment variable (default: ``false``):

Direct mode (MONETIZED_LINKS_ENABLED=false)
-------------------------------------------
* Returns the original canonical product URL unchanged.
* No affiliate tags, UTM parameters, or URL shortening are applied.
* No external monetisation API calls are made.

Monetised mode (MONETIZED_LINKS_ENABLED=true)
---------------------------------------------
* Applies store-specific affiliate programme tags.
* Appends UTM parameters for Google Analytics attribution.
* Optionally shortens the URL via Bitly (if ``BITLY_API_TOKEN`` is set).

Public API
----------
* ``build_direct_link(url)``      – return the URL as-is (direct mode).
* ``build_monetized_link(url, store)``  – return a fully tracked affiliate URL.
* ``build_offer_link(url, store)`` – delegate based on ``MONETIZED_LINKS_ENABLED``.
"""
from __future__ import annotations

import logging

from config import settings
from services.affiliate import get_affiliate_url

logger = logging.getLogger(__name__)


def build_direct_link(url: str) -> str:
    """Return *url* unchanged – no affiliate tags, UTM params, or shortening."""
    return url


def build_monetized_link(url: str, store: str) -> str:
    """
    Return a fully tracked affiliate URL for *url* from *store*.

    Applies the store's affiliate programme, UTM parameters, and optional
    Bitly shortening (see :func:`services.affiliate.get_affiliate_url`).
    """
    return get_affiliate_url(url, store)


def build_offer_link(url: str, store: str) -> str:
    """
    Return the appropriate offer URL based on ``MONETIZED_LINKS_ENABLED``.

    * ``MONETIZED_LINKS_ENABLED=false`` (default) → :func:`build_direct_link`
    * ``MONETIZED_LINKS_ENABLED=true``            → :func:`build_monetized_link`
    """
    if settings.MONETIZED_LINKS_ENABLED:
        logger.debug("Monetised link mode: building affiliate URL for %s (%s)", url, store)
        return build_monetized_link(url, store)
    logger.debug("Direct link mode: returning canonical URL for %s", url)
    return build_direct_link(url)
