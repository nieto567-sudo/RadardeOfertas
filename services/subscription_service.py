"""
User keyword subscription service.

When an offer is published, :func:`notify_subscribers` checks the
``user_subscriptions`` table and sends a personal Telegram DM to every
subscriber whose keyword appears in the product name (and whose optional
price ceiling / store filter is satisfied).
"""
from __future__ import annotations

import logging

import requests
from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, UserSubscription

logger = logging.getLogger(__name__)

_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"


# ── public API ────────────────────────────────────────────────────────────────


def add_subscription(
    db: Session,
    chat_id: int,
    keyword: str,
    *,
    max_price: float | None = None,
    store_filter: str | None = None,
) -> UserSubscription:
    """
    Create or re-activate a subscription for *chat_id* on *keyword*.

    If a row already exists (possibly inactive) it is updated in-place.
    The caller is responsible for committing.
    """
    keyword = keyword.strip().lower()
    sub = (
        db.query(UserSubscription)
        .filter_by(chat_id=chat_id, keyword=keyword)
        .first()
    )
    if sub is None:
        sub = UserSubscription(
            chat_id=chat_id,
            keyword=keyword,
            max_price=max_price,
            store_filter=store_filter,
            active=True,
        )
        db.add(sub)
    else:
        sub.active = True
        sub.max_price = max_price
        sub.store_filter = store_filter
    db.flush()
    return sub


def remove_subscription(db: Session, chat_id: int, keyword: str) -> bool:
    """
    Deactivate the subscription for *chat_id* on *keyword*.

    Returns ``True`` if a subscription was found and deactivated, ``False``
    when no matching active subscription exists.
    The caller is responsible for committing.
    """
    keyword = keyword.strip().lower()
    sub = (
        db.query(UserSubscription)
        .filter_by(chat_id=chat_id, keyword=keyword, active=True)
        .first()
    )
    if sub is None:
        return False
    sub.active = False
    db.flush()
    return True


def list_subscriptions(db: Session, chat_id: int) -> list[UserSubscription]:
    """Return all active subscriptions for *chat_id*."""
    return (
        db.query(UserSubscription)
        .filter_by(chat_id=chat_id, active=True)
        .order_by(UserSubscription.keyword)
        .all()
    )


def notify_subscribers(db: Session, offer: Offer) -> int:
    """
    Send a Telegram DM to every subscriber whose keyword matches the offer's
    product name.

    Returns the number of notifications sent.
    """
    product = offer.product
    if product is None:
        return 0

    name_lower = product.name.lower()
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — subscription alerts suppressed")
        return 0

    subs = db.query(UserSubscription).filter_by(active=True).all()
    sent = 0

    for sub in subs:
        # Keyword match
        if sub.keyword not in name_lower:
            continue
        # Optional price ceiling
        if sub.max_price is not None and offer.current_price > sub.max_price:
            continue
        # Optional store filter
        if sub.store_filter and product.store != sub.store_filter:
            continue

        _send_dm(token, sub.chat_id, offer)
        sent += 1

    return sent


# ── internal helpers ──────────────────────────────────────────────────────────


def _send_dm(token: str, chat_id: int, offer: Offer) -> None:
    """Send a personal DM to *chat_id* about *offer*."""
    product = offer.product
    url = offer.affiliate_url or product.url
    text = (
        f"🔔 *Alerta de oferta — {product.name}*\n\n"
        f"💰 Antes: ${offer.original_price:,.0f}\n"
        f"🔥 Ahora: ${offer.current_price:,.0f} "
        f"({offer.discount_pct:.0f}% descuento)\n"
        f"🏬 {product.store.replace('_', ' ').title()}\n\n"
        f"[🛒 Ver oferta]({url})"
    )
    try:
        resp = requests.post(
            _SEND_URL.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("DM to chat_id=%s failed: %s", chat_id, exc)
