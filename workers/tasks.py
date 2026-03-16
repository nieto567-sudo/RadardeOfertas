"""
Celery tasks.

Each task corresponds to one scraper (or a group of scrapers) and follows the
same pattern:

1. Run the scraper.
2. For every product, run the OfferProcessor pipeline.
3. For every qualifying offer, publish it to Telegram and notify subscribers.
4. Update scraper health record.
"""
from __future__ import annotations

import logging

from workers.celery_app import app
from database.connection import SessionLocal
from scrapers.manager import ScraperManager
from services.offer_processor import OfferProcessor
from services.scraper_health import record_scrape_result
from services.subscription_service import notify_subscribers
from telegram.publisher import TelegramPublisher

logger = logging.getLogger(__name__)


def _process_store(store_name: str) -> dict:
    """Shared logic: scrape one store, process products, publish offers."""
    manager = ScraperManager()

    scrape_error: str | None = None
    try:
        products = manager.run_store(store_name)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[%s] scrape failed: %s", store_name, exc)
        products = []
        scrape_error = str(exc)

    db = SessionLocal()
    publisher = TelegramPublisher()
    processor = OfferProcessor(db)

    offers_published = 0
    try:
        for product_data in products:
            offer = processor.process(product_data)
            if offer is not None:
                # Eager-load the product relationship before publishing
                db.refresh(offer)
                _ = offer.product  # ensure loaded
                publisher.publish(offer, db)
                notify_subscribers(db, offer)
                offers_published += 1

        # Update scraper health
        record_scrape_result(
            db,
            store_name,
            success=(scrape_error is None and len(products) > 0),
            products_found=len(products),
            error=scrape_error,
        )
        db.commit()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[%s] task error: %s", store_name, exc)
        db.rollback()
    finally:
        db.close()

    return {
        "store": store_name,
        "products_scraped": len(products),
        "offers_published": offers_published,
    }


# ── Individual store tasks ────────────────────────────────────────────────────
# All tasks use bind=True + max_retries=3 so transient failures are retried
# automatically with a 60-second back-off before being marked as failed.
# _process_store() handles all internal exceptions; the outer task only
# re-raises when an unexpected error escapes the helper.


@app.task(name="tasks.scrape_amazon", bind=True, max_retries=3)
def scrape_amazon(self):
    return _process_store("amazon")


@app.task(name="tasks.scrape_mercadolibre", bind=True, max_retries=3)
def scrape_mercadolibre(self):
    return _process_store("mercadolibre")


@app.task(name="tasks.scrape_walmart", bind=True, max_retries=3)
def scrape_walmart(self):
    return _process_store("walmart")


@app.task(name="tasks.scrape_liverpool", bind=True, max_retries=3)
def scrape_liverpool(self):
    return _process_store("liverpool")


@app.task(name="tasks.scrape_bodega_aurrera", bind=True, max_retries=3)
def scrape_bodega_aurrera(self):
    return _process_store("bodega_aurrera")


@app.task(name="tasks.scrape_costco", bind=True, max_retries=3)
def scrape_costco(self):
    return _process_store("costco")


@app.task(name="tasks.scrape_coppel", bind=True, max_retries=3)
def scrape_coppel(self):
    return _process_store("coppel")


@app.task(name="tasks.scrape_elektra", bind=True, max_retries=3)
def scrape_elektra(self):
    return _process_store("elektra")


@app.task(name="tasks.scrape_sears", bind=True, max_retries=3)
def scrape_sears(self):
    return _process_store("sears")


@app.task(name="tasks.scrape_sanborns", bind=True, max_retries=3)
def scrape_sanborns(self):
    return _process_store("sanborns")


@app.task(name="tasks.scrape_sams_club", bind=True, max_retries=3)
def scrape_sams_club(self):
    return _process_store("sams_club")


@app.task(name="tasks.scrape_office_depot", bind=True, max_retries=3)
def scrape_office_depot(self):
    return _process_store("office_depot")


@app.task(name="tasks.scrape_officemax", bind=True, max_retries=3)
def scrape_officemax(self):
    return _process_store("officemax")


@app.task(name="tasks.scrape_soriana", bind=True, max_retries=3)
def scrape_soriana(self):
    return _process_store("soriana")


@app.task(name="tasks.scrape_cyberpuerta", bind=True, max_retries=3)
def scrape_cyberpuerta(self):
    return _process_store("cyberpuerta")


@app.task(name="tasks.scrape_ddtech", bind=True, max_retries=3)
def scrape_ddtech(self):
    return _process_store("ddtech")


@app.task(name="tasks.scrape_pcel", bind=True, max_retries=3)
def scrape_pcel(self):
    return _process_store("pcel")


@app.task(name="tasks.scrape_intercompras", bind=True, max_retries=3)
def scrape_intercompras(self):
    return _process_store("intercompras")


@app.task(name="tasks.scrape_gameplanet", bind=True, max_retries=3)
def scrape_gameplanet(self):
    return _process_store("gameplanet")


@app.task(name="tasks.scrape_claro_shop", bind=True, max_retries=3)
def scrape_claro_shop(self):
    return _process_store("claro_shop")


@app.task(name="tasks.scrape_aliexpress", bind=True, max_retries=3)
def scrape_aliexpress(self):
    return _process_store("aliexpress")


@app.task(name="tasks.scrape_ebay", bind=True, max_retries=3)
def scrape_ebay(self):
    return _process_store("ebay")


@app.task(name="tasks.scrape_newegg", bind=True, max_retries=3)
def scrape_newegg(self):
    return _process_store("newegg")


@app.task(name="tasks.scrape_banggood", bind=True, max_retries=3)
def scrape_banggood(self):
    return _process_store("banggood")


@app.task(name="tasks.scrape_gearbest", bind=True, max_retries=3)
def scrape_gearbest(self):
    return _process_store("gearbest")


# ── Daily digest ──────────────────────────────────────────────────────────────


@app.task(name="tasks.publish_daily_digest", bind=True, max_retries=2)
def publish_daily_digest(self):
    """Publish the Top-N deal digest to the Telegram channel."""
    from database.connection import SessionLocal
    from services.daily_digest import publish_daily_digest as _run_digest

    db = SessionLocal()
    try:
        success = _run_digest(db)
        return {"success": success}
    except Exception as exc:  # pylint: disable=broad-except
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()
