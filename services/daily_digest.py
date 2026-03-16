"""
Daily deal digest.

Publishes a "Top N Ofertas del Día" summary to the Telegram channel once
a day (scheduled via Celery Beat).

The digest picks the top ``settings.DIGEST_TOP_N`` published offers from the
last 24 hours, sorted by score descending.  Each entry is a single line so
the message remains compact and scannable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.models import Offer, OfferStatus, Publication

logger = logging.getLogger(__name__)

_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"
_DIGEST_MAX_NAME_LENGTH = 50  # characters shown per offer line in the digest


def build_digest_text(db: Session, *, top_n: int | None = None) -> str | None:
    """
    Build the digest message text.

    Returns ``None`` when there are no qualifying offers in the last 24 h.
    """
    n = top_n or settings.DIGEST_TOP_N
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    offers = (
        db.query(Offer)
        .join(Publication, Offer.id == Publication.offer_id)
        .options(joinedload(Offer.product))
        .filter(
            Offer.status == OfferStatus.PUBLISHED,
            Publication.success.is_(True),
            Publication.sent_at >= cutoff,
        )
        .order_by(desc(Offer.score))
        .limit(n)
        .all()
    )

    if not offers:
        return None

    lines = [
        "🏆 *TOP OFERTAS DEL DÍA* 🏆",
        f"_(últimas 24 horas — {len(offers)} mejores deals)_",
        "",
    ]

    for i, offer in enumerate(offers, start=1):
        product = offer.product
        url = offer.affiliate_url or product.url
        store = product.store.replace("_", " ").title()
        name = product.name if len(product.name) <= _DIGEST_MAX_NAME_LENGTH else product.name[:_DIGEST_MAX_NAME_LENGTH - 3] + "…"
        lines.append(
            f"{i}\\. [{name}]({url})\n"
            f"   💰 ~~${offer.original_price:,.0f}~~ → *${offer.current_price:,.0f}* "
            f"\\(-{offer.discount_pct:.0f}%\\) · {store}"
        )

    lines += [
        "",
        "_Radar de Ofertas — las mejores ofertas de México_",
    ]
    return "\n".join(lines)


def publish_daily_digest(db: Session) -> bool:
    """
    Build and send the daily digest to the Telegram channel.

    Returns ``True`` on success, ``False`` otherwise.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    channel = settings.TELEGRAM_CHANNEL_ID
    if not token or not channel:
        logger.warning("Telegram not configured — daily digest skipped")
        return False

    text = build_digest_text(db)
    if text is None:
        logger.info("Daily digest: no qualifying offers in the last 24 h — skipped")
        return False

    try:
        resp = requests.post(
            _SEND_URL.format(token=token),
            json={
                "chat_id": channel,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Daily digest published successfully (%d chars)", len(text))
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Daily digest publish failed: %s", exc)
        return False
