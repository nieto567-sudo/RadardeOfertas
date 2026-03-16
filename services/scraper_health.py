"""
Scraper health monitoring service.

After every scraper run, call :func:`record_scrape_result` to update the
:class:`~database.models.ScraperHealth` row for that store.  When the
consecutive-failure count reaches ``SCRAPER_FAILURE_ALERT_THRESHOLD`` an
admin alert is sent to ``TELEGRAM_ADMIN_CHAT_ID`` via the Bot API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from config import settings
from database.models import ScraperHealth

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


def record_scrape_result(
    db: Session,
    store: str,
    *,
    success: bool,
    products_found: int = 0,
    error: str | None = None,
) -> ScraperHealth:
    """
    Update (or create) the :class:`ScraperHealth` row for *store*.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.  The caller is responsible for committing.
    store:
        Scraper store name (e.g. ``"walmart"``).
    success:
        ``True`` when the scraper returned at least one product without raising.
    products_found:
        Number of products returned by the scraper.
    error:
        Error message string when *success* is ``False``.
    """
    health = db.query(ScraperHealth).filter_by(store=store).first()
    if health is None:
        health = ScraperHealth(store=store)
        db.add(health)

    if success:
        health.consecutive_failures = 0
        health.last_success_at = datetime.now(tz=timezone.utc)
        health.last_products_found = products_found
        health.last_error = None
        health.is_healthy = True
    else:
        health.consecutive_failures = (health.consecutive_failures or 0) + 1
        health.last_error = error
        health.is_healthy = False

        threshold = settings.SCRAPER_FAILURE_ALERT_THRESHOLD
        if health.consecutive_failures >= threshold:
            _send_admin_alert(store, health.consecutive_failures, error)

    db.flush()
    return health


def _send_admin_alert(store: str, failures: int, error: str | None) -> None:
    """Send a Telegram message to the configured admin chat."""
    admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID
    token = settings.TELEGRAM_BOT_TOKEN
    if not admin_chat or not token:
        logger.warning(
            "Admin alert suppressed (TELEGRAM_ADMIN_CHAT_ID or "
            "TELEGRAM_BOT_TOKEN not configured): store=%s failures=%d",
            store,
            failures,
        )
        return

    text = (
        f"🚨 *Alerta de scraper*\n\n"
        f"🏬 Tienda: `{store}`\n"
        f"❌ Fallos consecutivos: {failures}\n"
        f"📝 Último error: `{error or 'desconocido'}`\n\n"
        f"Por favor revisa el servicio."
    )
    try:
        url = _API_BASE.format(token=token)
        resp = requests.post(
            url,
            json={
                "chat_id": admin_chat,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Admin alert sent for store=%s failures=%d", store, failures)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to send admin alert for %s: %s", store, exc)
