"""
Prometheus metrics for RadardeOfertas.

Metrics exposed
---------------
* ``radar_scrape_products_total``  – counter: products scraped, labelled by store
* ``radar_scrape_errors_total``    – counter: scraper errors, labelled by store
* ``radar_offers_processed_total`` – counter: offers through the pipeline, labelled by result
* ``radar_scrape_duration_seconds``– histogram: scrape cycle latency, labelled by store
* ``radar_cycle_duration_seconds`` – histogram: full run_once latency

HTTP metrics server
-------------------
Start the Prometheus HTTP server by calling :func:`start_metrics_server`.
The port defaults to ``9090`` and is configurable via ``PROMETHEUS_PORT``.

Usage
-----
    from services.metrics import (
        SCRAPE_PRODUCTS, SCRAPE_ERRORS,
        OFFERS_PROCESSED, SCRAPE_DURATION, CYCLE_DURATION,
        start_metrics_server,
    )
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (  # type: ignore[import]
        Counter,
        Histogram,
        start_http_server,
        REGISTRY,
    )

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.warning("prometheus_client not installed; metrics disabled")


# ── Metrics definitions ───────────────────────────────────────────────────────

if _AVAILABLE:
    SCRAPE_PRODUCTS = Counter(
        "radar_scrape_products_total",
        "Total products scraped",
        ["store"],
    )
    SCRAPE_ERRORS = Counter(
        "radar_scrape_errors_total",
        "Total scraper errors",
        ["store"],
    )
    OFFERS_PROCESSED = Counter(
        "radar_offers_processed_total",
        "Offers through the pipeline",
        ["result"],  # 'published' | 'discarded' | 'error'
    )
    SCRAPE_DURATION = Histogram(
        "radar_scrape_duration_seconds",
        "Time spent scraping one store",
        ["store"],
        buckets=[1, 5, 10, 30, 60, 120, 300],
    )
    CYCLE_DURATION = Histogram(
        "radar_cycle_duration_seconds",
        "Total run_once cycle duration",
        buckets=[5, 15, 30, 60, 120, 300, 600],
    )
else:
    # No-op stubs so imports never fail
    class _Stub:  # type: ignore[no-redef]
        def labels(self, **_):
            return self

        def inc(self, *_, **__):
            pass

        def observe(self, *_, **__):
            pass

        def time(self):
            import contextlib

            return contextlib.nullcontext()

    SCRAPE_PRODUCTS = _Stub()  # type: ignore[assignment]
    SCRAPE_ERRORS = _Stub()  # type: ignore[assignment]
    OFFERS_PROCESSED = _Stub()  # type: ignore[assignment]
    SCRAPE_DURATION = _Stub()  # type: ignore[assignment]
    CYCLE_DURATION = _Stub()  # type: ignore[assignment]


def start_metrics_server() -> None:
    """Start the Prometheus HTTP server on ``PROMETHEUS_PORT`` (default 9090)."""
    if not _AVAILABLE:
        logger.warning("prometheus_client not available; metrics server not started")
        return
    port = int(os.getenv("PROMETHEUS_PORT", "9090"))
    try:
        start_http_server(port)
        logger.info("Prometheus metrics server running on :%d/metrics", port)
    except OSError as exc:
        logger.error("Failed to start metrics server on port %d: %s", port, exc)
