"""
Telegram publisher.

Builds a richly formatted message for each offer and sends it to the
configured Telegram channel via the Bot API.

Message format uses Telegram Markdown (legacy mode) for compatibility.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings
from database.models import Offer, OfferType, Publication
from services.offer_scorer import OfferScorer
from services.price_comparison import compare_across_stores
from services.price_trend import get_price_trend, trend_emoji
from services.resale_detector import detect_resale_opportunity
from services.viral_detector import calculate_viral_score, viral_label

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"

# Thin separator line used between message sections
_SEP = "━━━━━━━━━━━━━━━━━━━━"


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
        message = self._build_message(offer, db)
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
    def _build_message(offer: Offer, db=None) -> str:
        product = offer.product
        url = offer.affiliate_url or product.url

        # ── Header ────────────────────────────────────────────────────────────
        label = _offer_label(offer.offer_type)
        lines = [f"{label}", ""]

        # ── Product info ──────────────────────────────────────────────────────
        lines.append(f"*{product.name}*")
        store_name = product.store.replace("_", " ").title()
        cat = product.category or "General"
        lines.append(f"🏬 {store_name}  |  🏷 {cat}")
        lines.append("")
        lines.append(_SEP)

        # ── Price block ───────────────────────────────────────────────────────
        saving = offer.original_price - offer.current_price
        lines += [
            f"💰 Precio habitual:  ${offer.original_price:>10,.0f} MXN",
            f"🔥 *Precio oferta:   ${offer.current_price:>10,.0f} MXN*",
            f"💸 *Ahorras:         ${saving:>10,.0f} MXN  ({offer.discount_pct:.0f}%)*",
            _SEP,
            "",
        ]

        # ── Signals ───────────────────────────────────────────────────────────
        signals: list[str] = []

        # Price trend
        if db is not None:
            trend = get_price_trend(db, product.id)
            emoji = trend_emoji(trend)
            if emoji:
                label_map = {"up": "subiendo", "down": "bajando", "flat": "estable"}
                signals.append(f"{emoji} Precio {label_map.get(trend or '', '')}")

        if offer.rapid_drop:
            signals.append("⚡ ¡Caída rápida de precio!")

        # Viral potential
        raw_vscore = getattr(offer, "viral_score", 0)
        vscore = raw_vscore if isinstance(raw_vscore, int) else 0
        vlabel = viral_label(vscore)
        if vlabel:
            signals.append(f"🚀 Potencial viral: {vlabel}")

        # Resale opportunity
        raw_rscore = getattr(offer, "resale_score", 0)
        rscore = raw_rscore if isinstance(raw_rscore, int) else 0
        if rscore >= 5:
            signals.append("🔄 Oportunidad de reventa detectada")

        # Score / quality badge
        score_label = OfferScorer.classify_score(offer.score)
        signals.append(f"⭐ Score: {offer.score}/100  ·  {score_label}")

        # Coupon
        if product.coupon_code:
            signals.append(f"🎟 Cupón: `{product.coupon_code}`")

        if signals:
            lines += signals
            lines.append("")

        # ── CTA button ────────────────────────────────────────────────────────
        lines.append(f"[🛒  *¡Comprar ahora →*]({url})")

        # ── Cross-store comparison ────────────────────────────────────────────
        if db is not None:
            comparison = compare_across_stores(db, product)
            if comparison and comparison.better_deal_exists:
                lines += [
                    "",
                    "🔍 *Comparativa de precios:*",
                ]
                for alt in comparison.alternatives[:3]:
                    marker = "✅" if abs(alt["price"] - comparison.cheapest_price) < 0.01 else "  "
                    lines.append(
                        f"{marker} [{alt['store']}]({alt['url']}) — "
                        f"${alt['price']:,.0f} MXN"
                    )
                lines.append(
                    f"\n💡 *Más barato en {comparison.cheapest_store}:* "
                    f"${comparison.cheapest_price:,.0f} MXN"
                )

        lines += ["", "_⚠️ Solo por tiempo limitado — precios sujetos a cambio_"]

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
        OfferType.PRICE_ERROR: "🚨🚨 *ERROR DE PRECIO DETECTADO* 🚨🚨",
        OfferType.EXCELLENT: "🔥🔥 *OFERTA EXCELENTE* 🔥🔥",
        OfferType.GOOD: "✅ *BUENA OFERTA*",
        OfferType.REGULAR: "ℹ️ *OFERTA DETECTADA*",
    }
    return mapping.get(offer_type, "🔥 *OFERTA DETECTADA*")
