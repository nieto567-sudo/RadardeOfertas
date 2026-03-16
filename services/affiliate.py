"""
Affiliate link generator.

Converts plain product URLs into affiliate / tracking URLs for the supported
programs:
    * Amazon Associates (amazon.com.mx)
    * MercadoLibre Affiliados (mercadolibre.com.mx)
    * AliExpress Portals
    * eBay Partner Network

For stores without a configured affiliate program the original URL is
returned unchanged.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from config import settings

logger = logging.getLogger(__name__)


def _rebuild_url(parsed, query_params: dict) -> str:
    """Return a URL string with *query_params* merged into the query string."""
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_affiliate_url(url: str, store: str) -> str:
    """
    Return an affiliate URL for *url* from *store*.

    Falls back to the original URL if no affiliate programme is configured
    for that store or if the required tag/id is not set.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)

        if store == "amazon":
            return _amazon(url, parsed, params)
        if store == "mercadolibre":
            return _mercadolibre(url, parsed, params)
        if store == "aliexpress":
            return _aliexpress(url, parsed, params)
        if store == "ebay":
            return _ebay(url, parsed, params)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Affiliate URL generation failed for %s (%s): %s", url, store, exc)

    return url


# ── Store-specific builders ───────────────────────────────────────────────────


def _amazon(url: str, parsed, params: dict) -> str:
    tag = settings.AMAZON_AFFILIATE_TAG
    if not tag:
        return url
    params["tag"] = [tag]
    # Ensure clean Amazon URL (remove ref= noise)
    params.pop("ref", None)
    params.pop("ref_", None)
    return _rebuild_url(parsed, {k: v[0] if len(v) == 1 else v for k, v in params.items()})


def _mercadolibre(url: str, parsed, params: dict) -> str:
    aff_id = settings.MERCADOLIBRE_AFFILIATE_ID
    if not aff_id:
        return url
    params["aff_id"] = [aff_id]
    params["aff_platform"] = ["radar"]
    return _rebuild_url(parsed, {k: v[0] if len(v) == 1 else v for k, v in params.items()})


def _aliexpress(url: str, parsed, params: dict) -> str:
    key = settings.ALIEXPRESS_AFFILIATE_KEY
    if not key:
        return url
    # AliExpress deep-link: https://portals.aliexpress.com/affiportals/web/portals.htm
    deep_link = f"https://portals.aliexpress.com/affiportals/web/portals.htm?aff_short_key={key}&url={url}"
    return deep_link


def _ebay(url: str, parsed, params: dict) -> str:
    campaign_id = settings.EBAY_CAMPAIGN_ID
    if not campaign_id:
        return url
    # eBay Partner Network rover link
    rover = (
        f"https://rover.ebay.com/rover/1/{campaign_id}/1?"
        f"mpre={url}"
    )
    return rover
