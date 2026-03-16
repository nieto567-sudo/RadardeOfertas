"""
Telegram bot entry point.

Starts a simple polling bot that responds to:
  /start       – welcome message
  /status      – system stats (products, offers)
  /ingresos    – estimated affiliate revenue summary
  /comisiones  – commission rate table per store
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger(__name__)


def run_bot() -> None:  # pragma: no cover
    """Start the Telegram bot in polling mode."""
    try:
        from telegram import Update  # type: ignore
        from telegram.ext import (  # type: ignore
            Application,
            CommandHandler,
            ContextTypes,
        )
    except ImportError:
        logger.error(
            "python-telegram-bot is not installed. "
            "Install it with: pip install python-telegram-bot"
        )
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "👋 Bienvenido a *RadardeOfertas*\\!\n\n"
            "Este bot publica automáticamente las mejores ofertas detectadas en "
            "tiendas de México y el mundo\\.\n\n"
            "Comandos disponibles:\n"
            "/status – estadísticas del sistema\n"
            "/ingresos – resumen de ingresos estimados\n"
            "/comisiones – tasas de comisión por tienda",
            parse_mode="MarkdownV2",
        )

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from database.connection import SessionLocal
        from database.models import Offer, Product

        db = SessionLocal()
        try:
            total_products = db.query(Product).count()
            total_offers = db.query(Offer).count()
            await update.message.reply_text(
                f"📊 *Estado del sistema*\n\n"
                f"🛍️ Productos monitoreados: {total_products:,}\n"
                f"🎯 Ofertas detectadas: {total_offers:,}",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show estimated affiliate revenue summary for the last 30 days."""
        from database.connection import SessionLocal
        from services.revenue_tracker import get_revenue_summary

        db = SessionLocal()
        try:
            summary = get_revenue_summary(db, days=30)
            total = summary["total_estimated_mxn"]
            count = summary["offers_published"]
            avg = summary["avg_per_offer_mxn"]
            by_network = summary["by_network"]
            by_store = summary["by_store"]

            network_lines = "\n".join(
                f"  • {net.replace('_', ' ').title()}: ${v:,.2f}"
                for net, v in by_network.items()
            ) or "  (sin datos)"

            store_lines = "\n".join(
                f"  • {s.replace('_', ' ').title()}: ${v:,.2f}"
                for s, v in by_store.items()
            ) or "  (sin datos)"

            text = (
                "💰 *Ingresos estimados — últimos 30 días*\n\n"
                f"📈 *Total estimado:* ${total:,.2f} MXN\n"
                f"🎯 *Ofertas publicadas:* {count:,}\n"
                f"📊 *Promedio por oferta:* ${avg:,.2f} MXN\n\n"
                f"🏦 *Por red de afiliados:*\n{network_lines}\n\n"
                f"🏬 *Top tiendas:*\n{store_lines}\n\n"
                "⚠️ _Estos valores son estimaciones basadas en tasas promedio de "
                "conversión de la industria. Los ingresos reales dependen de tu "
                "tasa de conversión y las ventas confirmadas en cada dashboard de "
                "afiliados._"
            )
            await update.message.reply_text(text, parse_mode="Markdown",
                                            disable_web_page_preview=True)
        finally:
            db.close()

    async def comisiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show commission rate table for all supported stores."""
        from services.revenue_tracker import get_commission_rates_text

        text = get_commission_rates_text()
        text += (
            "\n\n"
            "📝 *Cómo activar cada red:*\n"
            "• *Amazon Associates* → [associates.amazon.com.mx](https://associates.amazon.com.mx)\n"
            "• *MercadoLibre Afiliados* → [afiliados.mercadolibre.com](https://afiliados.mercadolibre.com)\n"
            "• *AliExpress Portals* → [portals.aliexpress.com](https://portals.aliexpress.com)\n"
            "• *eBay Partner Network* → [partnernetwork.ebay.com](https://partnernetwork.ebay.com)\n"
            "• *Admitad (Walmart, Liverpool, etc.)* → [admitad.com](https://www.admitad.com/en/publisher/)\n"
            "• *Bitly (rastreo de clics)* → [bitly.com](https://bitly.com)"
        )
        await update.message.reply_text(text, parse_mode="Markdown",
                                        disable_web_page_preview=True)

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ingresos", ingresos))
    app.add_handler(CommandHandler("comisiones", comisiones))

    logger.info("Telegram bot started (polling)…")
    app.run_polling()
