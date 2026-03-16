"""
Affiliate link generator.

Converts plain product URLs into tracked affiliate / monetised URLs.

Supported programmes
--------------------
* Amazon Associates       – amazon.com.mx   → AMAZON_AFFILIATE_TAG
* MercadoLibre Afiliados  – mercadolibre.com.mx → MERCADOLIBRE_AFFILIATE_ID
* AliExpress Portals      – aliexpress.com   → ALIEXPRESS_AFFILIATE_KEY
* eBay Partner Network    – ebay.com         → EBAY_CAMPAIGN_ID
* Admitad                 – Walmart MX, Liverpool, Coppel, Costco, Sam's Club,
                            Soriana, Office Depot, OfficeMax, Sears, Sanborns,
                            Elektra, PCEL, Cyberpuerta, and more.
                            → ADMITAD_PUBLISHER_ID + ADMITAD_SITE_IDS (JSON)

Additionally, every produced URL receives UTM parameters (for Google Analytics
tracking) and is optionally shortened via the Bitly API (for click counting).

For stores without any configured affiliate programme the original URL is
returned with only UTM parameters added.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, quote_plus

import requests as _requests

from config import settings

logger = logging.getLogger(__name__)

# ── Stores routed through Admitad ────────────────────────────────────────────
# Maps store_name → the key used to look up the Admitad site ID inside
# settings.ADMITAD_SITE_IDS.
_ADMITAD_STORES: dict[str, str] = {
    "walmart": "walmart",
    "bodega_aurrera": "bodega_aurrera",
    "liverpool": "liverpool",
    "costco": "costco",
    "coppel": "coppel",
    "elektra": "elektra",
    "sears": "sears",
    "sanborns": "sanborns",
    "sams_club": "sams_club",
    "office_depot": "office_depot",
    "officemax": "officemax",
    "soriana": "soriana",
    "cyberpuerta": "cyberpuerta",
    "pcel": "pcel",
    "ddtech": "ddtech",
    "intercompras": "intercompras",
    "gameplanet": "gameplanet",
    "claro_shop": "claro_shop",
}


# ── Public API ────────────────────────────────────────────────────────────────


def get_affiliate_url(url: str, store: str) -> str:
    """
    Return a fully tracked affiliate URL for *url* from *store*.

    Processing order
    ----------------
    1. Apply the affiliate programme for the store (if configured).
    2. Append UTM parameters (always).
    3. Shorten with Bitly (if BITLY_API_TOKEN is set).

    If any step raises an exception the original *url* is returned unchanged,
    so callers can always expect a valid URL string back.
    """
    try:
        affiliate = _apply_affiliate(url, store)
        tracked = _apply_utm(affiliate, store)
        return shorten_url(tracked)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Affiliate URL generation failed for %s (%s): %s", url, store, exc
        )
        return url


def shorten_url(url: str) -> str:
    """
    Shorten *url* via the Bitly API and return the short link.

    Returns the original URL unchanged if BITLY_API_TOKEN is not set or
    if the API call fails.
    """
    token = settings.BITLY_API_TOKEN
    if not token:
        return url
    try:
        payload: dict = {"long_url": url}
        if settings.BITLY_GROUP_GUID:
            payload["group_guid"] = settings.BITLY_GROUP_GUID
        resp = _requests.post(
            "https://api-ssl.bitly.com/v4/shorten",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("link", url)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Bitly shortening failed: %s", exc)
        return url


# ── Internal helpers ─────────────────────────────────────────────────────────


def _rebuild_url(parsed, query_params: dict) -> str:
    """Return a URL string with *query_params* merged into the query string."""
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _apply_affiliate(url: str, store: str) -> str:
    """Apply the appropriate affiliate programme and return the modified URL."""
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
    if store in _ADMITAD_STORES:
        return _admitad(url, store)

    return url


def _apply_utm(url: str, store: str) -> str:
    """
    Append UTM parameters to *url* for Google Analytics attribution.

    utm_source = settings.UTM_SOURCE  (default "radardeofertas")
    utm_medium = settings.UTM_MEDIUM  (default "telegram")
    utm_campaign = settings.UTM_CAMPAIGN  (default "oferta")
    utm_content = store name  (lets you filter per store in GA)
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["utm_source"] = [settings.UTM_SOURCE]
        params["utm_medium"] = [settings.UTM_MEDIUM]
        params["utm_campaign"] = [settings.UTM_CAMPAIGN]
        params["utm_content"] = [store]
        flat = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        return _rebuild_url(parsed, flat)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("UTM injection failed for %s: %s", url, exc)
        return url


# ── Store-specific builders ───────────────────────────────────────────────────


def _amazon(url: str, parsed, params: dict) -> str:
    tag = settings.AMAZON_AFFILIATE_TAG
    if not tag:
        return url
    params["tag"] = [tag]
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
    deep_link = (
        f"https://portals.aliexpress.com/affiportals/web/portals.htm"
        f"?aff_short_key={key}&url={url}"
    )
    return deep_link


def _ebay(url: str, parsed, params: dict) -> str:
    campaign_id = settings.EBAY_CAMPAIGN_ID
    if not campaign_id:
        return url
    return f"https://rover.ebay.com/rover/1/{campaign_id}/1?mpre={url}"


def _admitad(url: str, store: str) -> str:
    """
    Build an Admitad deep link for any store in the Admitad network.

    Deep-link format:
        https://ad.admitad.com/g/{site_id}/?i={publisher_id}&ulp={encoded_url}

    Requirements
    ------------
    * ADMITAD_PUBLISHER_ID – your Admitad publisher short code
    * ADMITAD_SITE_IDS – JSON dict mapping store_name → site_id
      Example: {"walmart": "abc123", "liverpool": "def456"}

    Sign up at https://www.admitad.com/en/publisher/
    Then search for each store in the 'Programmes' tab to get its site_id.
    """
    publisher_id = settings.ADMITAD_PUBLISHER_ID
    site_id = settings.ADMITAD_SITE_IDS.get(
        _ADMITAD_STORES.get(store, store), ""
    )
    if not publisher_id or not site_id:
        return url
    encoded_url = quote_plus(url)
    return (
        f"https://ad.admitad.com/g/{site_id}/"
        f"?i={publisher_id}&ulp={encoded_url}"
    )

