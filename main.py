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
import logging
import time

from database.connection import init_db
from scrapers.manager import ScraperManager
from services.offer_processor import OfferProcessor
from database.connection import SessionLocal
from telegram.publisher import TelegramPublisher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def run_once() -> None:
    """Run all scrapers once and process the results."""
    manager = ScraperManager()
    publisher = TelegramPublisher()
    db = SessionLocal()
    processor = OfferProcessor(db)

    logger.info("Starting scrape cycle…")
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
        choices=["run-once", "run-loop", "init-db"],
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
    args = parser.parse_args()

    if args.command == "init-db":
        logger.info("Initialising database…")
        init_db()
        logger.info("Database initialised.")
    elif args.command == "run-loop":
        init_db()
        run_loop(args.interval)
    else:
        init_db()
        run_once()


if __name__ == "__main__":
    main()
