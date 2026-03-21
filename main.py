"""
RadardeOfertas – main entry point.

Usage
-----
Run the full system locally (without Celery) using a simple polling loop::

    python main.py

Or start individual components:

    # Celery worker
    celery -A workers.celery_app worker --loglevel=info

    # Celery beat scheduler
    celery -A workers.celery_app beat --loglevel=info -S workers.scheduler

    # Telegram bot
    python -m telegram.bot
"""
from __future__ import annotations

import argparse
import sys
import time

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


def run_loop(interval_seconds: int = 300) -> None:
    """Continuously run the scraping cycle every *interval_seconds* seconds."""
    logger.info("Starting continuous loop (interval=%ds)…", interval_seconds)
    while True:
        run_once()
        logger.info("Sleeping %d seconds…", interval_seconds)
        time.sleep(interval_seconds)


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
        init_db()
        logger.info("Database initialised.")
    elif args.command == "run-loop":
        if args.metrics:
            start_metrics_server()
        init_db()
        run_loop(args.interval)
    else:
        if args.metrics:
            start_metrics_server()
        init_db()
        run_once()


if __name__ == "__main__":
    main()
