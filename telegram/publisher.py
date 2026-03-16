"""
Telegram publisher.

Builds a formatted message for each offer and sends it to the configured
Telegram channel via the Bot API.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings
from database.models import Offer, OfferType, Publication
from services.offer_scorer import OfferScorer

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramPublisher:
    """Sends offer notifications to a Telegram channel."""

    def __init__(self) -> None:
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
        self._base = _API_BASE.format(token=self.token)

    # ── public ────────────────────────────────────────────────────────────────

    def publish(self, offer: Offer, db) -> Publication:
        """
        Send *offer* to the Telegram channel and persist the result.

        Parameters
        ----------
        offer : Offer
            The ORM instance (with its ``.product`` relationship loaded).
        db :
            Active SQLAlchemy session used to persist the :class:`Publication`.
        """
        product = offer.product
        message = self._build_message(offer)
        pub = Publication(offer_id=offer.id)

        try:
            if product.image_url:
                result = self._send_photo(message, product.image_url)
            else:
                result = self._send_message(message)

            pub.telegram_message_id = result.get("message_id")
            pub.success = True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Telegram publish failed for offer %d: %s", offer.id, exc)
            pub.success = False
            pub.error_message = str(exc)

        db.add(pub)
        return pub

    # ── message builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_message(offer: Offer) -> str:
        product = offer.product
        label = _offer_label(offer.offer_type)
        url = offer.affiliate_url or product.url

        lines = [
            f"{label}",
            "",
            f"*{product.name}*",
            "",
            f"💰 *Antes:* ${offer.original_price:,.0f}",
            f"🔥 *Ahora:* ${offer.current_price:,.0f}",
            f"📉 *Descuento:* {offer.discount_pct:.0f}%",
            "",
            f"🏬 *Tienda:* {product.store.replace('_', ' ').title()}",
        ]

        if offer.rapid_drop:
            lines.append("⚡ *¡Caída rápida de precio!*")

        score_label = OfferScorer.classify_score(offer.score)
        lines.append(f"⭐ *Score:* {offer.score}/100 ({score_label})")
        lines.append("")
        lines.append(f"[🛒 Comprar aquí]({url})")

        return "\n".join(lines)

    # ── Telegram API calls ────────────────────────────────────────────────────

    def _send_message(self, text: str) -> dict:
        endpoint = f"{self._base}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        return self._post(endpoint, payload)

    def _send_photo(self, caption: str, photo_url: str) -> dict:
        endpoint = f"{self._base}/sendPhoto"
        payload = {
            "chat_id": self.channel_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "Markdown",
        }
        return self._post(endpoint, payload)

    @staticmethod
    def _post(endpoint: str, payload: dict) -> dict:
        resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data.get('description')}")
        return data.get("result", {})


# ── helpers ───────────────────────────────────────────────────────────────────


def _offer_label(offer_type: OfferType) -> str:
    mapping = {
        OfferType.PRICE_ERROR: "🚨 ERROR DE PRECIO DETECTADO",
        OfferType.EXCELLENT: "🔥 OFERTA EXCELENTE",
        OfferType.GOOD: "✅ BUENA OFERTA",
        OfferType.REGULAR: "ℹ️ OFERTA DETECTADA",
    }
    return mapping.get(offer_type, "🔥 OFERTA DETECTADA")
