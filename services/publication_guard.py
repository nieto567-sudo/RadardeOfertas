"""
Publication guard.

Central validation layer that decides whether an offer may be published to
Telegram.  Must be called *before* any Telegram API call.

Rules (evaluated in order)
--------------------------
1. Category whitelist   – offer category must be in ``ALLOWED_CATEGORIES``.
2. Valid price          – numeric and > 0.
3. Valid URL            – present and starts with ``http://`` or ``https://``.
4. No 24-hour duplicate – normalised URL must not have been published in the
                          last 24 hours (persisted in a JSON file).
5. Rate limit           – no more than ``MAX_PUBLICATIONS_PER_HOUR`` per hour
                          and at least ``MIN_SECONDS_BETWEEN_PUBLICATIONS``
                          between consecutive posts.

All discard reasons are logged at INFO level.  Successful publications are
also logged so there is always a full audit trail.

Discard reason codes
--------------------
``categoria_no_permitida``, ``categoria_vacia``, ``sin_precio``,
``precio_invalido``, ``sin_url``, ``url_invalida``, ``duplicado_24h``,
``rate_limited``, ``telegram_error``.

On successful publication: ``published``.

Dry-run mode
------------
When ``DRY_RUN=true`` the guard short-circuits at the Telegram-send step:
it logs the offer as *dry_run* but does **not** post anything to Telegram
and does **not** record the URL in the published-URLs store.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import settings

logger = logging.getLogger(__name__)

# ── Tracking parameters stripped during URL normalisation ────────────────────
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "ref", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid",
        "yclid", "msclkid", "_ga",
    }
)


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class GuardResult:
    """Outcome of :func:`can_publish`."""

    allowed: bool
    reason: str  # one of the documented reason codes


@dataclass
class _RateState:
    """In-memory rate-limit state (resets when the process restarts)."""

    last_publish_ts: float = 0.0
    window_start_ts: float = field(default_factory=time.monotonic)
    window_count: int = 0


# Module-level singleton — one per process.
_rate_state = _RateState()


# ── Public API ────────────────────────────────────────────────────────────────


def can_publish(
    url: str,
    price: Optional[float],
    category: Optional[str],
) -> GuardResult:
    """
    Return a :class:`GuardResult` indicating whether the offer may be published.

    Parameters
    ----------
    url:
        Raw product URL from the offer / product record.
    price:
        Current price of the offer (``None`` or ``0`` → rejected).
    category:
        Product category string (may be ``None`` or empty → rejected).
    """
    # 1. Category whitelist
    if not category or not category.strip():
        _log_discard("categoria_vacia", url, "category is empty or None")
        return GuardResult(allowed=False, reason="categoria_vacia")
    if category.strip() not in settings.ALLOWED_CATEGORIES:
        _log_discard(
            "categoria_no_permitida",
            url,
            f"category '{category}' not in whitelist",
        )
        return GuardResult(allowed=False, reason="categoria_no_permitida")

    # 2. Valid price
    if price is None:
        _log_discard("sin_precio", url, "price is None")
        return GuardResult(allowed=False, reason="sin_precio")
    try:
        price_val = float(price)
    except (TypeError, ValueError):
        _log_discard("precio_invalido", url, f"price cannot be parsed: {price!r}")
        return GuardResult(allowed=False, reason="precio_invalido")
    if price_val <= 0:
        _log_discard("precio_invalido", url, f"price is not positive: {price_val}")
        return GuardResult(allowed=False, reason="precio_invalido")

    # 3. Valid URL
    if not url or not url.strip():
        _log_discard("sin_url", url, "URL is empty")
        return GuardResult(allowed=False, reason="sin_url")
    if not url.strip().startswith(("http://", "https://")):
        _log_discard("url_invalida", url, f"URL does not start with http(s): {url!r}")
        return GuardResult(allowed=False, reason="url_invalida")

    # 4. 24-hour deduplication
    normalised = normalise_url(url)
    if is_duplicate(normalised):
        _log_discard("duplicado_24h", url, f"normalised URL already published: {normalised}")
        return GuardResult(allowed=False, reason="duplicado_24h")

    # 5. Rate limiting
    rate_result = _check_rate_limit()
    if rate_result is not None:
        _log_discard("rate_limited", url, rate_result)
        return GuardResult(allowed=False, reason="rate_limited")

    return GuardResult(allowed=True, reason="ok")


def record_published(url: str) -> None:
    """
    Persist *url* (normalised) in the 24-hour dedup store and update rate
    counters.  Call this *after* a successful Telegram send.
    """
    normalised = normalise_url(url)
    _add_to_published_store(normalised)
    _update_rate_state()
    logger.info("published | url=%s", normalised)


def normalise_url(url: str) -> str:
    """
    Return a canonical form of *url* by removing known tracking parameters.

    Scheme, host, path, and non-tracking query parameters are preserved.
    Fragment identifiers are stripped.

    Examples
    --------
    >>> normalise_url("https://example.com/p?id=1&utm_source=fb&ref=home")
    'https://example.com/p?id=1'
    """
    try:
        parsed = urlparse(url.strip())
        params = parse_qs(parsed.query, keep_blank_values=True)
        clean = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
        new_query = urlencode(clean, doseq=True)
        normalised = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, "")
        )
        return normalised
    except Exception:  # pylint: disable=broad-except
        return url.strip()


def is_duplicate(normalised_url: str) -> bool:
    """Return ``True`` if *normalised_url* was published in the last 24 hours."""
    store = _load_published_store()
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    return normalised_url in store and store[normalised_url] >= cutoff


# ── Internal helpers ──────────────────────────────────────────────────────────


def _log_discard(reason: str, url: str, detail: str) -> None:
    logger.info("discard | reason=%s | url=%s | detail=%s", reason, url, detail)


def _check_rate_limit() -> Optional[str]:
    """
    Enforce rate limits in memory.

    Returns a human-readable explanation string when the offer should be
    dropped, or ``None`` when it may proceed.
    """
    now = time.monotonic()

    # Minimum gap between consecutive publications
    gap = now - _rate_state.last_publish_ts
    if _rate_state.last_publish_ts > 0 and gap < settings.MIN_SECONDS_BETWEEN_PUBLICATIONS:
        return (
            f"only {gap:.1f}s since last publish "
            f"(min={settings.MIN_SECONDS_BETWEEN_PUBLICATIONS}s)"
        )

    # Rolling-window hourly cap
    window_age = now - _rate_state.window_start_ts
    if window_age > 3600:
        # Start a fresh window
        _rate_state.window_start_ts = now
        _rate_state.window_count = 0

    if _rate_state.window_count >= settings.MAX_PUBLICATIONS_PER_HOUR:
        return (
            f"hourly cap reached: {_rate_state.window_count} "
            f">= {settings.MAX_PUBLICATIONS_PER_HOUR}"
        )

    return None


def _update_rate_state() -> None:
    """Update in-memory rate-limit counters after a successful publish."""
    now = time.monotonic()
    window_age = now - _rate_state.window_start_ts
    if window_age > 3600:
        _rate_state.window_start_ts = now
        _rate_state.window_count = 0
    _rate_state.last_publish_ts = now
    _rate_state.window_count += 1


def _load_published_store() -> dict[str, str]:
    """
    Load the JSON store of recently published URLs.

    Returns a dict mapping ``normalised_url → ISO-8601 timestamp``.
    Returns an empty dict if the file does not exist or is corrupt.
    """
    path = settings.PUBLISHED_URLS_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read published-URLs store at %s; starting fresh", path)
        return {}


def _add_to_published_store(normalised_url: str) -> None:
    """
    Append *normalised_url* to the JSON store with the current UTC timestamp,
    then prune entries older than 24 hours to keep the file small.
    """
    store = _load_published_store()
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    store[normalised_url] = now_iso

    # Prune stale entries
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    store = {url: ts for url, ts in store.items() if ts >= cutoff}

    path = settings.PUBLISHED_URLS_FILE
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error("Could not write published-URLs store at %s: %s", path, exc)
