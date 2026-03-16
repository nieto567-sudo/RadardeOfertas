"""
Celery Beat schedule configuration.

Run with:
    celery -A workers.celery_app beat --loglevel=info
"""
from celery.schedules import crontab

from config.settings import (
    DIGEST_HOUR_UTC,
    DIGEST_MINUTE_UTC,
    SCHEDULE_AMAZON_SECONDS,
    SCHEDULE_MERCADOLIBRE_SECONDS,
    SCHEDULE_WALMART_SECONDS,
    SCHEDULE_LIVERPOOL_SECONDS,
    SCHEDULE_BODEGAAURRERA_SECONDS,
    SCHEDULE_DEFAULT_SECONDS,
)
from workers.celery_app import app


app.conf.beat_schedule = {
    # ── High-frequency (every 5 minutes) ──────────────────────────────────────
    "scrape-amazon": {
        "task": "tasks.scrape_amazon",
        "schedule": SCHEDULE_AMAZON_SECONDS,
    },
    "scrape-mercadolibre": {
        "task": "tasks.scrape_mercadolibre",
        "schedule": SCHEDULE_MERCADOLIBRE_SECONDS,
    },
    # ── Medium-frequency (every 10 minutes) ───────────────────────────────────
    "scrape-walmart": {
        "task": "tasks.scrape_walmart",
        "schedule": SCHEDULE_WALMART_SECONDS,
    },
    "scrape-liverpool": {
        "task": "tasks.scrape_liverpool",
        "schedule": SCHEDULE_LIVERPOOL_SECONDS,
    },
    "scrape-bodega-aurrera": {
        "task": "tasks.scrape_bodega_aurrera",
        "schedule": SCHEDULE_BODEGAAURRERA_SECONDS,
    },
    # ── Default frequency (every 15 minutes) ──────────────────────────────────
    "scrape-costco": {
        "task": "tasks.scrape_costco",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-coppel": {
        "task": "tasks.scrape_coppel",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-elektra": {
        "task": "tasks.scrape_elektra",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-sears": {
        "task": "tasks.scrape_sears",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-sanborns": {
        "task": "tasks.scrape_sanborns",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-sams-club": {
        "task": "tasks.scrape_sams_club",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-office-depot": {
        "task": "tasks.scrape_office_depot",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-officemax": {
        "task": "tasks.scrape_officemax",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-soriana": {
        "task": "tasks.scrape_soriana",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-cyberpuerta": {
        "task": "tasks.scrape_cyberpuerta",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-ddtech": {
        "task": "tasks.scrape_ddtech",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-pcel": {
        "task": "tasks.scrape_pcel",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-intercompras": {
        "task": "tasks.scrape_intercompras",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-gameplanet": {
        "task": "tasks.scrape_gameplanet",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-claro-shop": {
        "task": "tasks.scrape_claro_shop",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-aliexpress": {
        "task": "tasks.scrape_aliexpress",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-ebay": {
        "task": "tasks.scrape_ebay",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-newegg": {
        "task": "tasks.scrape_newegg",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-banggood": {
        "task": "tasks.scrape_banggood",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    "scrape-gearbest": {
        "task": "tasks.scrape_gearbest",
        "schedule": SCHEDULE_DEFAULT_SECONDS,
    },
    # ── Daily deal digest ──────────────────────────────────────────────────────
    "daily-digest": {
        "task": "tasks.publish_daily_digest",
        "schedule": crontab(hour=DIGEST_HOUR_UTC, minute=DIGEST_MINUTE_UTC),
    },
    # ── Pending offer publisher (every 10 min during smart hours) ─────────────
    "publish-pending-offers": {
        "task": "tasks.publish_pending_offers",
        "schedule": 600,  # every 10 minutes
    },
}
