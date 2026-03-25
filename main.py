"""
RadardeOfertas – main entry point.

Usage
-----
Run the full system locally (without Celery) using a simple polling loop::

    python main.py run-loop --interval 300

Or run a single cycle::

    python main.py run-once

Or start individual components (Celery mode, requires Redis):

    # Celery worker
    celery -A workers.celery_app worker --loglevel=info

    # Celery beat scheduler
    celery -A workers.celery_app beat --loglevel=info -S workers.scheduler

    # Telegram bot
    python -m telegram.bot
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import traceback

from services.logging_config import configure_logging

configure_logging()

import logging  # noqa: E402  (must come after configure_logging)

from database.connection import init_db
from scrapers.manager import ScraperManager
from services.offer_processor import OfferProcessor
from database.connection import SessionLocal
from telegram.publisher import TelegramPublisher
from services.metrics import CYCLE_DURATION, start_metrics_server

logger = logging.getLogger(__name__)

# ── Graceful-shutdown flag ────────────────────────────────────────────────────
_shutdown_requested = False


def _handle_signal(signum: int, frame: object) -> None:  # pragma: no cover  # noqa: ARG001
    global _shutdown_requested  # noqa: PLW0603
    sig_name = signal.Signals(signum).name
    logger.info("Received %s – finishing current cycle and shutting down…", sig_name)
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def run_once() -> None:
    """Run all scrapers once and process the results."""
    manager = ScraperManager()
    publisher = TelegramPublisher()
    db = SessionLocal()
    processor = OfferProcessor(db)

    logger.info("Starting scrape cycle…")
    with CYCLE_DURATION.time():
        products = manager.run_all()
        logger.info("Scraped %d products", len(products))

        offers_published = 0
        try:
            for product_data in products:
                offer = processor.process(product_data)
                if offer is not None:
                    db.refresh(offer)
                    _ = offer.product  # eagerly load relationship
                    publisher.publish(offer, db)
                    offers_published += 1
            db.commit()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error in run_once: %s", exc)
            db.rollback()
        finally:
            db.close()

    logger.info("Cycle complete. Offers published: %d", offers_published)


# Seconds to wait after a cycle-level exception before retrying.
_ERROR_BACKOFF_SECONDS = 60


def _interruptible_sleep(seconds: int) -> None:
    """Sleep for *seconds* in 1-second ticks so SIGTERM is honoured promptly."""
    for _ in range(seconds):
        if _shutdown_requested:
            break
        time.sleep(1)


def run_loop(interval_seconds: int = 300) -> None:
    """Continuously run the scraping cycle every *interval_seconds* seconds.

    Exceptions raised by individual cycles are caught, logged with a full
    traceback, and the loop sleeps for ``_ERROR_BACKOFF_SECONDS`` before
    retrying so that transient failures never stop the process.

    The loop honours SIGTERM / SIGINT: after receiving a signal it finishes
    (or skips) the current cycle and exits cleanly with code 0.
    """
    global _shutdown_requested  # noqa: PLW0603
    logger.info(
        "run-loop starting – interval=%ds, backoff_on_error=%ds",
        interval_seconds,
        _ERROR_BACKOFF_SECONDS,
    )
    iteration = 0
    while not _shutdown_requested:
        iteration += 1
        logger.info("run-loop heartbeat – iteration %d", iteration)
        try:
            run_once()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Unhandled exception in cycle %d (will retry after %ds):\n%s",
                iteration,
                _ERROR_BACKOFF_SECONDS,
                traceback.format_exc(),
            )
            _interruptible_sleep(_ERROR_BACKOFF_SECONDS)
            continue

        if _shutdown_requested:
            break

        logger.info("Sleeping %d seconds until next cycle…", interval_seconds)
        _interruptible_sleep(interval_seconds)

    logger.info("run-loop exiting cleanly after %d iteration(s).", iteration)


def _validate_env() -> list[str]:
    """Return a list of missing/empty required environment variable names."""
    required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]
    missing = [var for var in required if not os.environ.get(var, "").strip()]
    return missing


def main() -> None:
    parser = argparse.ArgumentParser(description="RadardeOfertas CLI")
    parser.add_argument(
        "command",
        choices=["run-once", "run-loop", "init-db", "healthcheck"],
        nargs="?",
        default="run-once",
        help="Command to execute (default: run-once)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Loop interval in seconds (only for run-loop, default: 300)",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        default=False,
        help="Start Prometheus metrics HTTP server (default port 9090)",
    )
    args = parser.parse_args()

    if args.command == "healthcheck":
        from services.healthcheck import run_healthcheck

        sys.exit(run_healthcheck())

    elif args.command == "init-db":
        logger.info("Initialising database…")
        try:
            init_db()
        except Exception:  # pylint: disable=broad-except
            logger.critical(
                "init-db failed:\n%s", traceback.format_exc()
            )
            sys.exit(1)
        logger.info("Database initialised.")
        sys.exit(0)

    elif args.command == "run-loop":
        missing = _validate_env()
        if missing:
            logger.critical(
                "run-loop cannot start: required environment variable(s) not set: %s. "
                "Set them in Railway → Service → Variables and redeploy.",
                ", ".join(missing),
            )
            sys.exit(1)

        if args.metrics:
            start_metrics_server()
        try:
            init_db()
        except Exception:  # pylint: disable=broad-except
            logger.critical(
                "run-loop: database initialisation failed:\n%s", traceback.format_exc()
            )
            sys.exit(1)

        run_loop(args.interval)
        sys.exit(0)

    else:  # run-once (default)
        if args.metrics:
            start_metrics_server()
        try:
            init_db()
        except Exception:  # pylint: disable=broad-except
            logger.critical(
                "run-once: database initialisation failed:\n%s", traceback.format_exc()
            )
            sys.exit(1)
        run_once()
        sys.exit(0)


if __name__ == "__main__":
    main()
