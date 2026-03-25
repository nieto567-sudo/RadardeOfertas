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
from services.price_sparkline import get_sparkline, is_all_time_low
from services.price_trend import get_price_trend, trend_emoji
from services.publication_guard import can_publish, record_published
from services.resale_detector import detect_resale_opportunity
from services.seasonal_events import get_season_banner
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

        The offer is validated by the publication guard before any Telegram
        API call is made.  Discarded offers are logged with the discard reason
        and a :class:`Publication` record is still returned (with
        ``success=False``) so callers always receive a consistent object.

        For ``PRICE_ERROR`` offers, a private notification is sent to
        ``TELEGRAM_ADMIN_CHAT_ID`` *before* the channel post, so the admin
        gets a heads-up about every pricing mistake detected.

        Parameters
        ----------
        offer : Offer
            The ORM instance (with its ``.product`` relationship loaded).
        db :
            Active SQLAlchemy session used to persist the :class:`Publication`.
        """
        product = offer.product
        url = offer.affiliate_url or product.url
        pub = Publication(offer_id=offer.id)

        # ── Publication guard ─────────────────────────────────────────────────
        guard = can_publish(
            url=url,
            price=offer.current_price,
            category=product.category,
        )
        if not guard.allowed:
            logger.info(
                "Offer %d discarded by publication guard: %s",
                offer.id,
                guard.reason,
            )
            pub.success = False
            pub.error_message = guard.reason
            db.add(pub)
            return pub

        # ── Dry-run mode ──────────────────────────────────────────────────────
        if settings.DRY_RUN:
            logger.info(
                "DRY_RUN active — offer %d would be published (url=%s)",
                offer.id,
                url,
            )
            pub.success = False
            pub.error_message = "dry_run"
            db.add(pub)
            return pub

        message = self._build_message(offer, db)

        # ── Admin pre-notification for price errors ───────────────────────────
        if (
            offer.offer_type == OfferType.PRICE_ERROR
            and settings.PRICE_ERROR_NOTIFY_ADMIN
        ):
            try:
                self._notify_admin_price_error(offer, message)
            except Exception as exc:  # pylint: disable=broad-except
                # Never let a failing admin notification block the channel post
                logger.error(
                    "Admin price-error notification raised unexpectedly "
                    "for offer %d: %s",
                    offer.id,
                    exc,
                )

        try:
            if product.image_url:
                result = self._send_photo(message, product.image_url)
            else:
                result = self._send_message(message)

            pub.telegram_message_id = result.get("message_id")
            pub.success = True
            record_published(url)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Telegram publish failed for offer %d: %s | reason=telegram_error",
                offer.id,
                exc,
            )
            pub.success = False
            pub.error_message = str(exc)

        db.add(pub)
        return pub

    def _notify_admin_price_error(self, offer: Offer, channel_message: str) -> None:
        """
        Send a private DM to the admin with the full offer details.

        This fires *before* the channel post so the admin always sees it first.
        Failures are logged but never propagate — the channel post must proceed.
        """
        admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID
        if not admin_chat:
            logger.debug(
                "Admin pre-notification skipped: TELEGRAM_ADMIN_CHAT_ID not set"
            )
            return

        product = offer.product
        url = offer.affiliate_url or product.url
        saving = offer.original_price - offer.current_price

        header = (
            "🚨 *ALERTA PRIVADA — Error de precio detectado*\n"
            "_(Se publicará automáticamente en el canal)_\n\n"
        )
        details = (
            f"🏬 *Tienda:* {product.store.replace('_', ' ').title()}\n"
            f"📦 *Producto:* {product.name}\n"
            f"💰 *Precio habitual:* ${offer.original_price:,.0f} MXN\n"
            f"🔥 *Precio error:* ${offer.current_price:,.0f} MXN\n"
            f"💸 *Ahorro:* ${saving:,.0f} MXN ({offer.discount_pct:.0f}%)\n"
            f"⭐ *Score:* {offer.score}/100\n"
            f"🔗 [Ver producto]({url})\n"
        )
        text = header + details

        endpoint = f"{self._base}/sendMessage"
        payload: dict = {
            "chat_id": admin_chat,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        # Also send the product photo to the admin if available
        if product.image_url:
            try:
                photo_endpoint = f"{self._base}/sendPhoto"
                self._post(
                    photo_endpoint,
                    {
                        "chat_id": admin_chat,
                        "photo": product.image_url,
                        "caption": text,
                        "parse_mode": "Markdown",
                    },
                )
                logger.info(
                    "Admin price-error notification (with photo) sent for offer %d",
                    offer.id,
                )
                return
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Admin photo notification failed for offer %d, "
                    "falling back to text: %s",
                    offer.id,
                    exc,
                )

        try:
            self._post(endpoint, payload)
            logger.info(
                "Admin price-error notification sent for offer %d", offer.id
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Admin price-error notification failed for offer %d: %s",
                offer.id,
                exc,
            )

    # ── message builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_message(offer: Offer, db=None) -> str:
        product = offer.product
        url = offer.affiliate_url or product.url

        # ── Seasonal banner (only during special Mexican shopping events) ─────
        banner = get_season_banner()
        lines: list[str] = []
        if banner:
            lines += [f"*{banner}*", ""]

        # ── Header ────────────────────────────────────────────────────────────
        label = _offer_label(offer.offer_type)
        lines += [f"{label}", ""]

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
        ]

        # All-time low badge (shown when the current price is the lowest ever)
        if db is not None:
            try:
                if is_all_time_low(db, product.id, offer.current_price):
                    lines.append("🏆 *¡PRECIO MÍNIMO HISTÓRICO!*")
            except Exception:  # pylint: disable=broad-except
                pass

        # Price sparkline
        if db is not None:
            try:
                sparkline = get_sparkline(db, product.id)
                if sparkline:
                    lines.append(f"📈 Historial: `{sparkline}`")
            except Exception:  # pylint: disable=broad-except
                pass

        lines += [_SEP, ""]

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
