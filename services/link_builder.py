"""
Link builder – decides between direct and monetized offer URLs.

Two operating modes are controlled by the ``MONETIZED_LINKS_ENABLED``
environment variable (default: ``false``):

Direct mode (MONETIZED_LINKS_ENABLED=false, default)
-----------------------------------------------------
* Returns the original canonical product URL unchanged.
* No affiliate tags or tracking parameters are applied.
* No external API calls are made.

Monetized mode (MONETIZED_LINKS_ENABLED=true)
----------------------------------------------
* Delegates to :func:`services.affiliate.get_affiliate_url`.
* Implement the desired affiliate programme(s) in ``services/affiliate.py``
  before enabling this mode.

Public API
----------
* ``build_direct_link(url)``           – return the URL as-is (direct mode).
* ``build_monetized_link(url, store)`` – return a monetized URL (future use).
* ``build_offer_link(url, store)``     – delegate based on ``MONETIZED_LINKS_ENABLED``.
"""
from __future__ import annotations

import logging

from config import settings
from services.affiliate import get_affiliate_url

logger = logging.getLogger(__name__)


def build_direct_link(url: str) -> str:
    """Return *url* unchanged – no affiliate tags or tracking parameters."""
    return url


def build_monetized_link(url: str, store: str) -> str:
    """
    Return a monetized URL for *url* from *store*.

    Delegates to :func:`services.affiliate.get_affiliate_url`.  Implement the
    desired affiliate programme there before setting ``MONETIZED_LINKS_ENABLED=true``.
    """
    return get_affiliate_url(url, store)


def build_offer_link(url: str, store: str) -> str:
    """
    Return the appropriate offer URL based on ``MONETIZED_LINKS_ENABLED``.

    * ``MONETIZED_LINKS_ENABLED=false`` (default) → :func:`build_direct_link`
    * ``MONETIZED_LINKS_ENABLED=true``            → :func:`build_monetized_link`
    """
    if settings.MONETIZED_LINKS_ENABLED:
        logger.debug("Monetized link mode: building affiliate URL for %s (%s)", url, store)
        return build_monetized_link(url, store)
    logger.debug("Direct link mode: returning canonical URL for %s", url)
    return build_direct_link(url)
