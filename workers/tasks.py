"""
Celery tasks.

Each task corresponds to one scraper (or a group of scrapers) and follows the
same pattern:

1. Run the scraper.
2. For every product, run the OfferProcessor pipeline.
3. For every qualifying offer, publish it to Telegram.
"""
from __future__ import annotations

import logging

from workers.celery_app import app
from database.connection import SessionLocal
from scrapers.manager import ScraperManager
from services.offer_processor import OfferProcessor
from telegram.publisher import TelegramPublisher

logger = logging.getLogger(__name__)


def _process_store(store_name: str) -> dict:
    """Shared logic: scrape one store, process products, publish offers."""
    manager = ScraperManager()
    products = manager.run_store(store_name)

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
                offers_published += 1
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


@app.task(name="tasks.scrape_amazon", bind=True, max_retries=3)
def scrape_amazon(self):
    try:
        return _process_store("amazon")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.scrape_mercadolibre", bind=True, max_retries=3)
def scrape_mercadolibre(self):
    try:
        return _process_store("mercadolibre")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.scrape_walmart", bind=True, max_retries=3)
def scrape_walmart(self):
    try:
        return _process_store("walmart")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.scrape_liverpool", bind=True, max_retries=3)
def scrape_liverpool(self):
    try:
        return _process_store("liverpool")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.scrape_bodega_aurrera", bind=True, max_retries=3)
def scrape_bodega_aurrera(self):
    try:
        return _process_store("bodega_aurrera")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.scrape_costco")
def scrape_costco():
    return _process_store("costco")


@app.task(name="tasks.scrape_coppel")
def scrape_coppel():
    return _process_store("coppel")


@app.task(name="tasks.scrape_elektra")
def scrape_elektra():
    return _process_store("elektra")


@app.task(name="tasks.scrape_sears")
def scrape_sears():
    return _process_store("sears")


@app.task(name="tasks.scrape_sanborns")
def scrape_sanborns():
    return _process_store("sanborns")


@app.task(name="tasks.scrape_sams_club")
def scrape_sams_club():
    return _process_store("sams_club")


@app.task(name="tasks.scrape_office_depot")
def scrape_office_depot():
    return _process_store("office_depot")


@app.task(name="tasks.scrape_officemax")
def scrape_officemax():
    return _process_store("officemax")


@app.task(name="tasks.scrape_soriana")
def scrape_soriana():
    return _process_store("soriana")


@app.task(name="tasks.scrape_cyberpuerta")
def scrape_cyberpuerta():
    return _process_store("cyberpuerta")


@app.task(name="tasks.scrape_ddtech")
def scrape_ddtech():
    return _process_store("ddtech")


@app.task(name="tasks.scrape_pcel")
def scrape_pcel():
    return _process_store("pcel")


@app.task(name="tasks.scrape_intercompras")
def scrape_intercompras():
    return _process_store("intercompras")


@app.task(name="tasks.scrape_gameplanet")
def scrape_gameplanet():
    return _process_store("gameplanet")


@app.task(name="tasks.scrape_claro_shop")
def scrape_claro_shop():
    return _process_store("claro_shop")


@app.task(name="tasks.scrape_aliexpress")
def scrape_aliexpress():
    return _process_store("aliexpress")


@app.task(name="tasks.scrape_ebay")
def scrape_ebay():
    return _process_store("ebay")


@app.task(name="tasks.scrape_newegg")
def scrape_newegg():
    return _process_store("newegg")


@app.task(name="tasks.scrape_banggood")
def scrape_banggood():
    return _process_store("banggood")


@app.task(name="tasks.scrape_gearbest")
def scrape_gearbest():
    return _process_store("gearbest")
