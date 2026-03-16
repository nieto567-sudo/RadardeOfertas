"""
Weekly deal savings summary.

Published once a week (configurable day/hour via env vars) to the Telegram
channel.  Highlights:

* Total offers published in the last 7 days
* Total potential savings in MXN across all published deals
* Average discount percentage
* Most active store
* Best individual deal (highest score)
* A social share call-to-action

The summary serves as social proof and encourages subscribers to share the
channel with friends — one of the most effective growth levers for a deal
channel.
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


def build_weekly_summary_text(db: Session) -> str | None:
    """
    Build the weekly summary message text.

    Returns ``None`` when there are no published offers in the last 7 days.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)

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
        .all()
    )

    if not offers:
        return None

    total_offers = len(offers)
    total_savings = sum(o.original_price - o.current_price for o in offers)
    avg_discount = sum(o.discount_pct for o in offers) / total_offers

    # Top store by offer count
    store_counts: dict[str, int] = {}
    for o in offers:
        store = o.product.store.replace("_", " ").title()
        store_counts[store] = store_counts.get(store, 0) + 1
    top_store = max(store_counts, key=lambda s: store_counts[s])

    # Best deal this week (highest score)
    best = offers[0]  # already ordered by score desc
    best_name = (
        best.product.name[:42] + "…"
        if len(best.product.name) > 42
        else best.product.name
    )
    best_url = best.affiliate_url or best.product.url
    best_saving = best.original_price - best.current_price

    # Date range label (consistent dd/mm/YYYY format for both ends)
    week_start = (datetime.now(tz=timezone.utc) - timedelta(days=7)).strftime("%d/%m/%Y")
    week_end = datetime.now(tz=timezone.utc).strftime("%d/%m/%Y")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "📅 *RESUMEN SEMANAL DE OFERTAS*",
        f"_{week_start} – {week_end}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🎯 *{total_offers}* ofertas publicadas",
        f"💰 *${total_savings:,.0f} MXN* en ahorros potenciales",
        f"📉 Descuento promedio: *{avg_discount:.0f}%*",
        f"🏬 Tienda más activa: *{top_store}*",
        "",
        "🏆 *Mejor deal de la semana:*",
        f"[{best_name}]({best_url})",
        f"   💸 *{best.discount_pct:.0f}% OFF* · Ahorro *${best_saving:,.0f} MXN*",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🤩 ¿Conoces a alguien que ame ahorrar?",
        "*¡Comparte este canal con tus amigos!* 👇",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def publish_weekly_summary(db: Session) -> bool:
    """
    Build and send the weekly summary to the Telegram channel.

    Returns ``True`` on success, ``False`` otherwise.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    channel = settings.TELEGRAM_CHANNEL_ID
    if not token or not channel:
        logger.warning("Telegram not configured — weekly summary skipped")
        return False

    text = build_weekly_summary_text(db)
    if text is None:
        logger.info("Weekly summary: no qualifying offers in the last 7 days — skipped")
        return False

    try:
        resp = requests.post(
            _SEND_URL.format(token=token),
            json={
                "chat_id": channel,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Weekly summary published (%d chars)", len(text))
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Weekly summary publish failed: %s", exc)
        return False
