"""
Circuit breaker for scrapers.

State is persisted in Redis so it survives worker restarts.
Each scraper gets an independent breaker keyed by its ``store_name``.

States
------
* **closed**   – normal operation (requests allowed)
* **open**     – too many recent failures; requests are blocked until cooldown passes
* **half-open** – cooldown has expired; next request is a probe

Configuration (env vars)
------------------------
* ``CIRCUIT_BREAKER_FAILURE_THRESHOLD`` – consecutive failures before opening (default 5)
* ``CIRCUIT_BREAKER_COOLDOWN_SECONDS``  – seconds to wait before switching to half-open (default 300)

Usage
-----
    from services.circuit_breaker import CircuitBreaker, CircuitOpen

    cb = CircuitBreaker("amazon")
    if cb.is_open():
        # skip scraping this store
        ...
    try:
        products = scraper.scrape()
        cb.record_success()
    except Exception as exc:
        cb.record_failure()
        raise
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
_COOLDOWN_SECONDS = int(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "300"))

# Redis key prefixes
_KEY_FAILURES = "cb:failures:{store}"
_KEY_OPENED_AT = "cb:opened_at:{store}"
_KEY_PAUSED = "cb:paused:{store}"  # manual admin pause


class CircuitOpen(Exception):
    """Raised when a request is attempted while the circuit is open."""


class CircuitBreaker:
    """
    Per-store circuit breaker backed by Redis.

    Falls back to in-process counters when Redis is unavailable, so the
    scraper continues operating even without a Redis connection.
    """

    def __init__(self, store: str, redis_client=None) -> None:
        self.store = store
        self._redis = redis_client or _get_redis()
        # In-process fallback (used when Redis is unavailable)
        self._local_failures: int = 0
        self._local_opened_at: Optional[float] = None

    # ── public API ────────────────────────────────────────────────────────────

    def is_open(self) -> bool:
        """Return True if this store's circuit is open (scraping should be skipped)."""
        # Manual admin pause always wins
        if self._is_manually_paused():
            return True

        opened_at = self._get_opened_at()
        if opened_at is None:
            return False  # circuit is closed

        elapsed = time.time() - opened_at
        if elapsed >= _COOLDOWN_SECONDS:
            # Transition to half-open: allow one probe
            self._clear_opened_at()
            logger.info("[circuit_breaker] %s → half-open (probe allowed)", self.store)
            return False

        remaining = int(_COOLDOWN_SECONDS - elapsed)
        logger.debug(
            "[circuit_breaker] %s is OPEN; %ds remaining", self.store, remaining
        )
        return True

    def record_success(self) -> None:
        """Reset the failure counter (circuit closes)."""
        self._set_failures(0)
        self._clear_opened_at()
        self._local_failures = 0
        self._local_opened_at = None
        logger.debug("[circuit_breaker] %s → closed (success recorded)", self.store)

    def record_failure(self) -> None:
        """Increment failures; open circuit if threshold is reached."""
        failures = self._increment_failures()
        logger.debug(
            "[circuit_breaker] %s failure #%d (threshold=%d)",
            self.store,
            failures,
            _FAILURE_THRESHOLD,
        )
        if failures >= _FAILURE_THRESHOLD:
            self._set_opened_at(time.time())
            logger.warning(
                "[circuit_breaker] %s → OPEN after %d consecutive failures",
                self.store,
                failures,
            )

    def get_status(self) -> dict:
        """Return a status dict for healthchecks and admin commands."""
        paused = self._is_manually_paused()
        opened_at = self._get_opened_at()
        failures = self._get_failures()
        state = "closed"
        if paused:
            state = "paused"
        elif opened_at is not None:
            elapsed = time.time() - opened_at
            state = "open" if elapsed < _COOLDOWN_SECONDS else "half-open"
        return {
            "store": self.store,
            "state": state,
            "failures": failures,
            "cooldown_seconds": _COOLDOWN_SECONDS,
            "failure_threshold": _FAILURE_THRESHOLD,
        }

    # ── admin controls ────────────────────────────────────────────────────────

    def pause(self) -> None:
        """Manually pause this store (admin command)."""
        if self._redis:
            try:
                self._redis.set(_KEY_PAUSED.format(store=self.store), "1")
                logger.info("[circuit_breaker] %s manually PAUSED", self.store)
                return
            except Exception as exc:
                logger.warning("[circuit_breaker] Redis error on pause: %s", exc)
        self._local_opened_at = time.time() + 10 ** 9  # effectively forever

    def resume(self) -> None:
        """Resume a manually paused store and reset failure counter."""
        if self._redis:
            try:
                self._redis.delete(_KEY_PAUSED.format(store=self.store))
                self._set_failures(0)
                self._clear_opened_at()
                logger.info("[circuit_breaker] %s RESUMED", self.store)
                return
            except Exception as exc:
                logger.warning("[circuit_breaker] Redis error on resume: %s", exc)
        self._local_failures = 0
        self._local_opened_at = None

    # ── Redis helpers (with in-process fallback) ──────────────────────────────

    def _is_manually_paused(self) -> bool:
        if self._redis:
            try:
                return bool(self._redis.exists(_KEY_PAUSED.format(store=self.store)))
            except Exception:
                pass
        return False

    def _get_failures(self) -> int:
        if self._redis:
            try:
                val = self._redis.get(_KEY_FAILURES.format(store=self.store))
                return int(val) if val else 0
            except Exception:
                pass
        return self._local_failures

    def _increment_failures(self) -> int:
        if self._redis:
            try:
                return int(
                    self._redis.incr(_KEY_FAILURES.format(store=self.store))
                )
            except Exception:
                pass
        self._local_failures += 1
        return self._local_failures

    def _set_failures(self, value: int) -> None:
        if self._redis:
            try:
                self._redis.set(_KEY_FAILURES.format(store=self.store), value)
                return
            except Exception:
                pass
        self._local_failures = value

    def _get_opened_at(self) -> Optional[float]:
        if self._redis:
            try:
                val = self._redis.get(_KEY_OPENED_AT.format(store=self.store))
                return float(val) if val else None
            except Exception:
                pass
        return self._local_opened_at

    def _set_opened_at(self, ts: float) -> None:
        if self._redis:
            try:
                self._redis.set(_KEY_OPENED_AT.format(store=self.store), ts)
                return
            except Exception:
                pass
        self._local_opened_at = ts

    def _clear_opened_at(self) -> None:
        if self._redis:
            try:
                self._redis.delete(_KEY_OPENED_AT.format(store=self.store))
                return
            except Exception:
                pass
        self._local_opened_at = None


# ── module-level helpers ──────────────────────────────────────────────────────

_redis_instance = None


def _get_redis():
    """Return a shared Redis connection or None if unavailable."""
    global _redis_instance  # pylint: disable=global-statement
    if _redis_instance is not None:
        return _redis_instance
    try:
        import redis as redis_lib  # type: ignore[import]
        from config.settings import REDIS_URL

        _redis_instance = redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis_instance.ping()  # eager connect to catch misconfig early
        return _redis_instance
    except Exception as exc:
        logger.warning(
            "[circuit_breaker] Redis unavailable; using in-process fallback: %s", exc
        )
        return None


def get_all_statuses() -> list[dict]:
    """Return circuit breaker status for every known store (from Redis keys)."""
    r = _get_redis()
    stores: set[str] = set()
    if r:
        try:
            for key in r.scan_iter("cb:*"):
                parts = key.split(":", 2)
                if len(parts) == 3:
                    stores.add(parts[2])
        except Exception:
            pass
    return [CircuitBreaker(s).get_status() for s in sorted(stores)]
